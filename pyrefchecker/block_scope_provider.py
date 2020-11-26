from contextlib import contextmanager
from typing import Iterator, List, Optional, Set, Union

import libcst as cst
import libcst.metadata as meta
import libcst.metadata.scope_provider as sp
from libcst.helpers import get_full_name_for_node


class BlockScopeProvider(meta.ScopeProvider):
    """ A ScopeProvider which provides treats  scopes """

    def visit_Module(self, node: cst.Module) -> Optional[bool]:
        visitor = BlockScopeVisitor(self)
        node.visit(visitor)
        visitor.infer_accesses()
        return None


class BlockScope(sp.LocalScope):
    """ A Block scope, e.g. for If, Try """


def find_qualified_name_for_non_import(
    assignment: sp.Assignment, remaining_name: str
) -> Set[sp.QualifiedName]:
    """ A modified version of 'find_qualified_name_for_non_import' which handles BlockScope """

    scope = assignment.scope
    name_prefixes: List[str] = []
    while scope:
        if isinstance(scope, sp.ClassScope):
            if scope.name:
                name_prefixes.append(scope.name)
        elif isinstance(scope, sp.FunctionScope):
            name_prefixes.append(f"{scope.name}.<locals>")
        elif isinstance(scope, sp.GlobalScope):
            break
        elif isinstance(scope, sp.ComprehensionScope):
            name_prefixes.append("<comprehension>")
        elif isinstance(scope, BlockScope):
            pass
        else:
            raise Exception(f"Unexpected Scope: {scope}")
        scope = scope.parent

    parts = [*reversed(name_prefixes)]
    if remaining_name:
        parts.append(remaining_name)
    return {sp.QualifiedName(".".join(parts), sp.QualifiedNameSource.LOCAL)}


@contextmanager
def monkeypatch_nameutil() -> Iterator[None]:
    """ Patch _NameUtil so that it can handle BlockScopes """

    prop = "find_qualified_name_for_non_import"
    prev = getattr(sp._NameUtil, prop, None)
    setattr(
        sp._NameUtil, prop, find_qualified_name_for_non_import,
    )
    try:
        yield
    finally:
        setattr(sp._NameUtil, prop, prev)


EXIT_NODES = (cst.Raise, cst.Return, cst.Continue, cst.Break)

EXIT_FUNCTIONS = ("sys.exit", "os._exit")


def is_exit_expression(node: cst.CSTNode, scope: sp.Scope) -> bool:
    """
    Return true if the node is a function call which unconditionally causes the application to exit.

    - Function calls to builtin exit functions
    - Function calls to functions with NoReturn type
    - Function calls to functions which are terminal
    """

    if isinstance(node, cst.Expr) and isinstance(node.value, cst.Call):
        # Builtin exit functions
        qualified_names = scope.get_qualified_names_for(node.value.func)
        for qname in qualified_names:
            if (
                qname.name in EXIT_FUNCTIONS
                and qname.source == sp.QualifiedNameSource.IMPORT
            ):
                return True

        # Custom exit functions
        for assignment in scope.assignments[node.value.func]:
            if assignment.node.returns:
                return_annotation_names = scope.get_qualified_names_for(
                    assignment.node.returns.annotation
                )
                if (
                    sp.QualifiedName(
                        name="typing.NoReturn", source=sp.QualifiedNameSource.IMPORT,
                    )
                    in return_annotation_names
                ):
                    return True

            # Terminal function bodies
            for statement in getattr(assignment.node.body, "body", []):
                if isinstance(statement, cst.SimpleStatementLine):
                    for statement_item in getattr(statement, "body", []):
                        if is_exit_expression(statement_item, assignment.scope):
                            return True
    return False


def is_terminal(node: cst.CSTNode, scope: sp.Scope) -> bool:
    """
    Return true if a node's body includes any unconditioinal statements which break control out of the current scope.

    Currently this includes:
        - Statements: continue, raise, return, break
        - Anything which causes the application to quit

    """

    for statement in getattr(node.body, "body", []):
        if isinstance(statement, cst.SimpleStatementLine):
            for statement_item in getattr(statement, "body", []):
                if isinstance(statement_item, EXIT_NODES):
                    return True

                if is_exit_expression(statement_item, scope):
                    return True

    return False


class BlockScopeVisitor(sp.ScopeVisitor):
    """ A ScopeVisitor which also makes scopes for blocks """

    def visit_For(self, node: cst.For) -> Optional[bool]:
        node.target.visit(self)
        node.iter.visit(self)

        with self._new_scope(BlockScope, node, get_full_name_for_node(node.body)):
            node.body.visit(self)

        if node.orelse:
            with self._new_scope(
                BlockScope, node.orelse, get_full_name_for_node(node.body)
            ):
                node.orelse.visit(self)

        return False

    def visit_If(self, node: cst.If) -> Optional[bool]:
        """ Create a new scope for if """
        node.test.visit(self)

        if is_conditional_typing_import(node, self.scope):
            node.body.visit(self)
            return False

        orelse = node.orelse

        terminal_else = False

        while orelse:
            if isinstance(orelse, cst.If):
                orelse = orelse.orelse
            elif isinstance(orelse, cst.Else):
                if is_terminal(orelse, self.scope):
                    terminal_else = True
                break

        if terminal_else:
            # If the last else includes a bare 'raise' or 'return',
            # we just assume that variables defined in the if/else statements
            # *will be* accessible after the If statement.

            # TODO: in theory we could improve this by assuming that only the set of
            # assignments common to all if/elif blocks is available after the else block.

            node.body.visit(self)
            orelse = node.orelse
            while orelse:
                orelse.body.visit(self)
                orelse = getattr(orelse, "orelse", None)
        else:
            with self._new_scope(BlockScope, node, get_full_name_for_node(node.body)):
                node.body.visit(self)

            if node.orelse:
                node.orelse.visit(self)

        return False

    def visit_Try(self, node: cst.Try) -> Optional[bool]:
        """ Deal with the complexities of try/except/else/finally """

        all_terminal_handlers = all(
            is_terminal(handler, self.scope) for handler in node.handlers
        )

        if all_terminal_handlers:
            # If all except handlers are terminal, assume that anything defined in the body WILL be seen
            # if we make it past the try block

            node.body.visit(self)
        else:
            with self._new_scope(
                BlockScope, node.body, get_full_name_for_node(node.body)
            ):
                node.body.visit(self)

        if node.handlers and len(node.handlers) == 1:
            # If there is only one exception handler, and it does not terminate
            # then any variables declared in it will be enabled after it.
            # Therefore, do not create a new scope
            node.handlers[0].visit(self)

        else:
            # Otherwise, we don't know which handler will be called (if any),
            # therefore we need to create a new scope for each one
            for handler in node.handlers:
                with self._new_scope(
                    BlockScope, handler, get_full_name_for_node(node.body)
                ):
                    handler.visit(self)

        if node.orelse:
            with self._new_scope(
                BlockScope, node.orelse, get_full_name_for_node(node.body)
            ):
                # An else block only runs if the try block succeeded
                # Therefore, run the try block inside the else scope!
                node.body.visit(self)
                node.orelse.visit(self)

        if node.finalbody:
            # Finally is always run, so its variables are visible to subsequent code
            # Therefore it is visited in the current scope
            node.finalbody.visit(self)

        return False


def is_conditional_typing_import(node: cst.If, scope: sp.LocalScope):
    """
    Return true if an if statement was a truth check of typing.TYPE_CHECKING.
    """

    if node.orelse:
        return False

    tested = node.test
    if is_truth_comparison(node.test, scope):
        tested = node.test.left

    for qname in scope.get_qualified_names_for(tested):
        if (
            qname.name == "typing.TYPE_CHECKING"
            and qname.source == sp.QualifiedNameSource.IMPORT
        ):
            return True

    return False


def is_truth_comparison(node: cst.CSTNode, scope: sp.Scope):
    """ Return true if the node is a comparison of the form "x is True" or "x == True" """
    if not isinstance(node, cst.Comparison):
        return False

    if len(node.comparisons) != 1:
        return False

    comp = node.comparisons[0]
    if isinstance(comp.operator, (cst.Is, cst.Equal)):
        if scope.get_qualified_names_for(comp.comparator) == {
            sp.QualifiedName(
                name="builtins.True", source=sp.QualifiedNameSource.BUILTIN
            )
        }:
            return True
