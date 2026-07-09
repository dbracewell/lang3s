from typing import Callable, TypeVar

T = TypeVar("T")


def binary_search(data: list[T], match_func: Callable[[T], int]) -> int:
    low = 0
    high = len(data) - 1

    while low <= high:
        mid = (low + high) // 2
        current_item = data[mid]

        # match_func should return:
        #  0 if match
        # -1 if target is smaller than current (look left)
        #  1 if target is larger than current (look right)
        result = match_func(current_item)

        if result == 0:
            return mid  # Found it!
        elif result < 0:
            high = mid - 1
        else:
            low = mid + 1

    return -1  # Not found


def hashed_select(name: str, items: list[T]) -> T:
    hash_val = 0

    for char in name:
        hash_val = (hash_val << 5) - hash_val + ord(char)
        hash_val = hash_val & 0xFFFFFFFF
        if hash_val >= 0x80000000:
            hash_val -= 0x100000000

    index = abs(hash_val) % len(items)
    return items[index]
