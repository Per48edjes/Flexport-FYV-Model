def substring_list_match(string_list, substr_list):
    return [
        target_str for target_str in string_list
        if any(search_str in target_str for search_str in substr_list)
    ]


def rev_dict_replace(value: str, mapping: dict) -> str:
    for k, v in mapping.items():
        if value in v:
            return k
    return None
