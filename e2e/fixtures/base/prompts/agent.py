SYSTEM_PROMPT = """
You are a support agent. Answer only from the knowledge base.
Reply in the customer's language.
"""


def build(question: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
