import difflib
import re


def words_of(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def match_token(text: str, token: str) -> bool:
    token = token.strip()
    if not token:
        return False
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1].lower() in text
    fuzzy = token.startswith("~") or token.endswith("~")
    token = token.strip("~")
    if "*" in token:
        pattern = re.compile(r"\b" + re.escape(token).replace(r"\*", r"\w*") + r"\b", re.IGNORECASE)
        return bool(pattern.search(text))
    if fuzzy:
        return bool(difflib.get_close_matches(token.lower(), words_of(text), n=1, cutoff=0.78))
    return token.lower() in text


def proximity_match(text: str, left: str, right: str, distance: int) -> bool:
    word_list = words_of(text)

    def positions(phrase: str) -> list[int]:
        parts = words_of(phrase.strip('"'))
        if not parts:
            return []
        width = len(parts)
        return [i for i in range(len(word_list) - width + 1) if word_list[i : i + width] == parts]

    left_positions = positions(left)
    right_positions = positions(right)
    return any(abs(a - b) <= distance for a in left_positions for b in right_positions)


def _split_top_level(query: str, operator: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    in_quote = False
    buffer: list[str] = []
    index = 0
    while index < len(query):
        char = query[index]
        if char == '"':
            in_quote = not in_quote
            buffer.append(char)
            index += 1
            continue
        if not in_quote and char == "(":
            depth += 1
        elif not in_quote and char == ")":
            depth -= 1
        if not in_quote and depth == 0 and query[index : index + len(operator)].upper() == operator:
            parts.append("".join(buffer).strip())
            buffer = []
            index += len(operator)
            continue
        buffer.append(char)
        index += 1
    parts.append("".join(buffer).strip())
    return [part for part in parts if part]


def compile_query(query: str):
    proximity_pattern = re.compile(r'(".*?"|[\w~*]+)\s+(?:W|NEAR)/(\d+)\s+(".*?"|[\w~*]+)', re.IGNORECASE)

    def evaluate(text: str, expression: str) -> bool:
        expression = expression.strip()
        if not expression:
            return False
        if expression.startswith("(") and expression.endswith(")"):
            inner = expression[1:-1].strip()
            if inner:
                return evaluate(text, inner)
        or_parts = _split_top_level(expression, " OR ")
        if len(or_parts) > 1:
            return any(evaluate(text, part) for part in or_parts)
        and_not_parts = _split_top_level(expression, " AND NOT ")
        if len(and_not_parts) > 1:
            return evaluate(text, and_not_parts[0]) and all(not evaluate(text, part) for part in and_not_parts[1:])
        and_parts = _split_top_level(expression, " AND ")
        if len(and_parts) > 1:
            return all(evaluate(text, part) for part in and_parts)
        not_parts = _split_top_level(expression, " NOT ")
        if len(not_parts) > 1:
            return evaluate(text, not_parts[0]) and all(not evaluate(text, part) for part in not_parts[1:])
        if expression.upper().startswith("NOT "):
            return not evaluate(text, expression[4:])
        proximity = proximity_pattern.fullmatch(expression)
        if proximity:
            return proximity_match(text, proximity.group(1), proximity.group(3), int(proximity.group(2)))
        return match_token(text, expression)

    return lambda text: evaluate(text, query)


def run_search(index: dict, terms: list[str]) -> dict:
    results: dict[str, dict] = {}
    for raw_term in terms:
        term = (raw_term or "").strip()
        if not term:
            continue
        matcher = compile_query(term)
        documents = []
        total_hits = 0
        for doc_name, payload in index.items():
            matches = []
            for chunk in payload.get("chunks", []):
                normalized = chunk.get("text", "").lower()
                if matcher(normalized):
                    matches.append(
                        {
                            "id": chunk["id"],
                            "label": chunk["label"],
                            "page": chunk.get("page"),
                            "snippet": chunk.get("snippet", ""),
                        }
                    )
            if matches:
                documents.append(
                    {
                        "name": doc_name,
                        "title": payload.get("title", doc_name.split("/")[-1]),
                        "matches": matches,
                        "match_count": len(matches),
                    }
                )
                total_hits += len(matches)
        documents.sort(key=lambda item: (-item["match_count"], item["name"].lower()))
        results[term] = {"total_hits": total_hits, "document_count": len(documents), "documents": documents}
    return results
