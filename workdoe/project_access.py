PRIVATE_MEDIA_EMBEDDING_HEADERS = {
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Frame-Options": "DENY",
}


def private_media_embedding_blocked(fetch_site: str, fetch_mode: str, fetch_dest: str) -> bool:
    """Keep direct navigation available without treating browser metadata as authorization."""
    return fetch_site in {"same-site", "cross-site"} and (fetch_mode, fetch_dest) != ("navigate", "document")


def contractor_can_view_project(
    status: str,
    client_status: str,
    *,
    has_approved_match: bool,
    participates: bool,
) -> bool:
    """Allow open leads or the viewer's own history, but never hidden projects."""
    if client_status != "active" or status not in {"open", "closed"}:
        return False
    return (status == "open" and not has_approved_match) or participates
