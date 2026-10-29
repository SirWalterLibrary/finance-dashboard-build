"""Scope logic: which accounts are visible to which user (SPEC "Scope rules")."""


def owner_ids(scope: str, user_id) -> list:
    """Return the owner_user_id values visible for `scope` as a list.

    personal -> [user_id]
    joint    -> [None]
    combined -> [None, user_id]
    Invalid scope -> ValueError (router maps to 400).
    """
    if scope == "personal":
        return [user_id]
    if scope == "joint":
        return [None]
    if scope == "combined":
        return [None, user_id]
    raise ValueError(f"invalid scope: {scope!r}")


def owner_clause(scope: str, user_id, column: str = "owner_user_id") -> tuple:
    """Return (sql_fragment, params) for filtering accounts by scope.

    NULL-safe: a joint account (owner IS NULL) must never be leaked to a
    personal scope, and a personal account must never be visible outside its
    owner. Invalid scope -> ValueError (router maps to 400).
    """
    if scope == "personal":
        return f"({column} = ?)", (user_id,)
    if scope == "joint":
        return f"({column} IS NULL)", ()
    if scope == "combined":
        return f"({column} IS NULL OR {column} = ?)", (user_id,)
    raise ValueError(f"invalid scope: {scope!r}")
