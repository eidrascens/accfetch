from random import choice
from string import ascii_lowercase, ascii_uppercase, digits


def id_gen() -> str:
    return "".join(
            choice(
                ascii_lowercase + ascii_uppercase + digits
            ) for _ in range(8)
        )
