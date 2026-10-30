def _normalize_whitespace(value: str) -> str:
    normalized = " ".join(value.split())

    if not normalized:
        raise ValueError("Value cannot be empty")

    return normalized


def normalize_company_name(company_name: str) -> str:
    return _normalize_whitespace(company_name).upper()


def normalize_role_title(role_title: str) -> str:
    return _normalize_whitespace(role_title).lower()