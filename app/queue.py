from collections import deque
from typing import List
from app.models import QueueItem

def insert_at(deq, index, item):
    deq.rotate(-index)
    deq.appendleft(item)
    deq.rotate(index)
    
def add_before(deq: deque, index: int, item):
    """
    Insert item before the given index.
    """
    if index < 0 or index > len(deq):
        raise IndexError("Index out of bounds")
    deq.rotate(-index)
    deq.appendleft(item)
    deq.rotate(index)

def add_after(deq: deque, index: int, item):
    """
    Insert item after the given index.
    """
    if index < -1 or index >= len(deq):
        raise IndexError("Index out of bounds")
    deq.rotate(-(index + 1))
    deq.appendleft(item)
    deq.rotate(index + 1)
    

def add_multiple_extend(deq: deque, items: List[QueueItem]):
    """
    Extends the deque with multiple QueueItem objects.
    
    Args:
        deq (deque): The target deque to add items to.
        items (List[QueueItem]): A list of QueueItem instances.
    """
    deq.extend(items)
    
    
def clear_queue(deq: deque):
    """Removes all items from the queue."""
    deq.clear()

def get_song_at(deq: deque, index: int):
    """Returns the item at the given index."""
    if index < 0 or index >= len(deq):
        raise IndexError("Index out of bounds")
    return deq[index]

def queue_to_json(deq: deque):
    """Returns the queue items as a JSON-serializable list."""
    return list(deq)  # If you want to serialize: return json.dumps(list(deq))


queue = deque()

# TODO: Implement this by threading library instead of asybcio
# def wait_until_finished(
#     player_type: str,
#     song_name: str,
#     on_finish: Optional[Callable[[], None]] = None
# ):
#     def _watcher():
#         while get_playerctl_data(player_type).get("media_name") == song_name:
#             time.sleep(2)

#         print("Song finished!")
#         if on_finish:
#             on_finish()  # ✅ Call it only if provided

    # threading.Thread(target=_watcher, daemon=True).start()

"""
popleft() does two things:

    Retrieves the leftmost item (the "front" of the queue, like the first person in line).

    Removes that item from the deque.
"""

if __name__ == "__main__":
    # TEST
    queue.append("Song 1")
    print(queue)
    queue.append("Song 2")
    queue.append("Song 3")
    queue.append("Song 4")
    print(queue)
    
    queue.append("Song 5")
    print(queue)
    
    queue.append("Song 6")
    
    print(queue)
    
    # REMINDER: index always starts from zero
    
    # Peek at the next item (without removing it)
    print(queue[0])  # Output: Song 1    
    
        # Remove the first item (FIFO behavior)
    next_song = queue.popleft()
    print(next_song)  # Output: Song 1
    print(queue)
    
    # Add to the left side (optional)
    queue.appendleft("Urgent Song")
    
    insert_at(queue, 1, 'songRef')
    
    print(queue)
    
    # So this will add the song before "songRef"
    add_before(queue, 1, "before song")
    
    print(queue)
    
    # So this should add the song after "songRef"
    add_after(queue, 2, "after song")
    

    print(queue)
    
    print(queue_to_json(queue))