"""Pure publication eligibility rules shared by publishers and tests."""


def publication_block_reason(deal, existing_post=None) -> str | None:
    """Return why a deal must not be published, or None when it is eligible."""
    if (getattr(deal, "status", None) or "").strip().lower() == "cancelled":
        return f"Deal {deal.id} is cancelled and cannot be published."

    if existing_post is not None:
        return f"Deal {deal.id} is already posted."

    return None
