import libcst as cst
import libcst.metadata.scope_provider as sp

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
            if not isinstance(assignment, sp.Assignment):
                continue
            if not isinstance(assignment.node, cst.FunctionDef):
                continue
            if assignment.node.returns:
                return_annotation_names = scope.get_qualified_names_for(
                    assignment.node.returns.annotation
                )
                if (
                    sp.QualifiedName(
                        name="typing.NoReturn",
                        source=sp.QualifiedNameSource.IMPORT,
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

    for statement in getattr(getattr(node, "body", None), "body", []):
        if isinstance(statement, cst.SimpleStatementLine):
            for statement_item in getattr(statement, "body", []):
                if isinstance(statement_item, EXIT_NODES):
                    return True

                if is_exit_expression(statement_item, scope):
                    return True

    return False


def is_conditional_typing_import(node: cst.If, scope: sp.Scope) -> bool:
    """
    Return true if an if statement was a truth check of typing.TYPE_CHECKING.
    """

    if node.orelse:
        return False

    tested = node.test

    if isinstance(node.test, cst.Comparison) and is_truth_comparison(node.test, scope):
        tested = node.test.left

    for qname in scope.get_qualified_names_for(tested):
        if (
            qname.name == "typing.TYPE_CHECKING"
            and qname.source == sp.QualifiedNameSource.IMPORT
        ):
            return True

    return False


def is_truth_comparison(node: cst.Comparison, scope: sp.Scope) -> bool:
    """ Return true if the node is a comparison of the form "x is True" or "x == True" """

    if len(node.comparisons) != 1:
        return False

    comp = node.comparisons[0]
    return isinstance(
        comp.operator, (cst.Is, cst.Equal)
    ) and scope.get_qualified_names_for(comp.comparator) == {
        sp.QualifiedName(name="builtins.True", source=sp.QualifiedNameSource.BUILTIN)
    }
