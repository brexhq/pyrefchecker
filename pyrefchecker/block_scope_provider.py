from typing import List, Optional, Set, Union

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


def monkeypatch_nameutil() -> None:
    """ Patch _NameUtil so that it can handle BlockScopes """

    setattr(
        sp._NameUtil,
        "find_qualified_name_for_non_import",
        find_qualified_name_for_non_import,
    )


EXIT_NODES = (cst.Raise, cst.Return, cst.Continue, cst.Break)


def is_terminal(node: Union[cst.Else, cst.ExceptHandler]) -> bool:
    """
    Return true if the Else or Except node includes any unconditioinal statements which break control out of the current scope.

    Currently: continue, raise, return, break
    There might be more?
    """

    for statement in getattr(node.body, "body", []):
        if isinstance(statement, cst.SimpleStatementLine):
            for statement_item in getattr(statement, "body", []):
                if isinstance(statement_item, EXIT_NODES):
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

        orelse = node.orelse

        terminal_else = False

        while orelse:
            if isinstance(orelse, cst.If):
                orelse = orelse.orelse
            elif isinstance(orelse, cst.Else):
                if is_terminal(orelse):
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

        # If an "Else" has a bare raise or return, the

        return False

    def visit_Try(self, node: cst.Try) -> Optional[bool]:
        """ Deal with the complexities of try/except/else/finally """

        all_terminal_handlers = all(is_terminal(handler) for handler in node.handlers)

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
