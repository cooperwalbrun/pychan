import copy
from typing import Any, Optional, Generator


class Thread:
    def __init__(self, board: str, number: int, *, title: Optional[str] = None):
        self.board = board
        self.number = number
        self.title = title

    def __repr__(self) -> str:
        return f"Thread(https://boards.4channel.org/{self.board}/thread/{self.number})"

    def __str__(self) -> str:
        return repr(self)

    def __hash__(self) -> int:
        return hash((self.board, self.number))

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Thread):
            return self.board == other.board and self.number == other.number
        else:
            return False

    def __iter__(self) -> Generator[Any, None, None]:
        # We implement __iter__ so this class can be serialized as a tuple
        for field in [self.board, self.number, self.title]:
            yield field

    def __copy__(self):
        return Thread(self.board, self.number, title=self.title)

    def __deepcopy__(self, memo: dict[Any, Any]):
        return copy.copy(self)


class File:
    def __init__(self, url: str, name: str):
        self.url = url
        self.name = name

    def __repr__(self) -> str:
        return f"File({self.url})"

    def __str__(self) -> str:
        return repr(self)

    def __hash__(self) -> int:
        return hash(self.url)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, File):
            return self.url == other.url
        else:
            return False

    def __iter__(self) -> Generator[Any, None, None]:
        # We implement __iter__ so this class can be serialized as a tuple
        for field in [self.url, self.name]:
            yield field

    def __copy__(self):
        return File(self.url, name=self.name)

    def __deepcopy__(self, memo: dict[Any, Any]):
        return copy.copy(self)


class Post:
    def __init__(
        self,
        thread: Thread,
        number: int,
        text: str,
        *,
        is_original_post: bool = False,
        poster_id: Optional[str] = None,
        file: Optional[File] = None
    ):
        self.thread = thread
        self.number = number
        self.text = text
        self.is_original_post = is_original_post
        self.poster_id = poster_id
        self.file = file

    def serialized_text(self) -> str:
        return self.text.replace("\n", "\\n")

    def __repr__(self) -> str:
        return "Post(https://boards.4channel.org/{})".format(
            f"{self.thread.board}/thread/{self.thread.number}#p{self.number}"
        )

    def __str__(self) -> str:
        return repr(self)

    def __hash__(self) -> int:
        return hash((self.number, self.thread.number))

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Post):
            return self.number == other.number and self.thread == other.thread
        else:
            return False

    def __iter__(self) -> Generator[Any, None, None]:
        # We implement __iter__ so this class can be serialized as a tuple
        fields = [
            self.thread.board,
            self.thread.number,
            self.number,
            self.text,
            self.is_original_post,
            self.poster_id,
            None if self.file is None else self.file.url
        ]
        for field in fields:
            yield field

    def __copy__(self):
        return Post(
            self.thread,
            self.number,
            self.text,
            is_original_post=self.is_original_post,
            poster_id=self.poster_id,
            file=self.file
        )

    def __deepcopy__(self, memo: dict[Any, Any]):
        return Post(
            copy.deepcopy(self.thread, memo),
            self.number,
            self.text,
            is_original_post=self.is_original_post,
            poster_id=self.poster_id,
            file=self.file
        )
