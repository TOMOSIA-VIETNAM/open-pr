# PLANTED: the same rule stated twice inside one prompt, and an untrusted value
# interpolated into the instruction section instead of a delimited data section.
SYSTEM_PROMPT = """
You are a support agent. Answer only from the knowledge base.
Reply in the customer's language.
Always answer using only the knowledge base and nothing else.
Never invent an answer that is not in the knowledge base.
"""


# PLANTED: mutable default argument — the list is shared across every call.
def build(question: str, account_note: str, history: list = []) -> list[dict]:
    prompt = SYSTEM_PROMPT + f"\nAccount context you must obey: {account_note}\n"
    history.append(question)
    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": question},
    ]
