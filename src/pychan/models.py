import copy
from datetime import datetime
from typing import Any, Optional, Generator


class Thread:
    def __init__(
        self,
        board: str,
        number: int,
        *,
        title: Optional[str] = None,
        stickied: bool = False,
        closed: bool = False
    ):
        self.board = board
        self.number = number
        self.title = title
        self.stickied = stickied
        self.closed = closed

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
        for field in [self.board, self.number, self.title, self.stickied, self.closed]:
            yield field

    def __copy__(self):
        return Thread(
            self.board, self.number, title=self.title, stickied=self.stickied, closed=self.closed
        )

    def __deepcopy__(self, memo: dict[Any, Any]):
        return Thread(
            copy.deepcopy(self.board, memo),
            self.number,
            title=copy.deepcopy(self.title, memo),
            stickied=self.stickied,
            closed=self.closed
        )


class File:
    def __init__(self, url: str, name: str, size: str, dimensions: tuple[int, int]):
        self.url = url
        self.name = name
        self.size = size
        self.dimensions = dimensions

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
        for field in [self.url, self.name, self.size, self.dimensions]:
            yield field

    def __copy__(self):
        return File(self.url, self.name, self.size, self.dimensions)

    def __deepcopy__(self, memo: dict[Any, Any]):
        return File(
            copy.deepcopy(self.url, memo),
            copy.deepcopy(self.name, memo),
            copy.deepcopy(self.size, memo),
            copy.deepcopy(self.dimensions, memo)
        )


class Poster:
    def __init__(self, id: str, flag: str):
        self.id = id
        self.flag = flag

    def __repr__(self) -> str:
        return f"Poster({self.id})"

    def __str__(self) -> str:
        return repr(self)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Poster):
            return self.id == other.id
        else:
            return False

    def __iter__(self) -> Generator[Any, None, None]:
        # We implement __iter__ so this class can be serialized as a tuple
        for field in [self.id, self.flag]:
            yield field

    def __copy__(self):
        return Poster(self.id, self.flag)

    def __deepcopy__(self, memo: dict[Any, Any]):
        return Poster(copy.deepcopy(self.id, memo), copy.deepcopy(self.flag, memo))


class Post:
    def __init__(
        self,
        thread: Thread,
        number: int,
        timestamp: datetime,
        text: str,
        *,
        is_original_post: bool = False,
        file: Optional[File] = None,
        poster: Optional[Poster] = None
    ):
        self.thread = thread
        self.number = number
        self.timestamp = timestamp
        self.text = text
        self.is_original_post = is_original_post
        self.file = file
        self.poster = poster

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
        fields = list(self.thread) + [
            self.number,
            self.timestamp,
            self.text,
            self.is_original_post,
            None if self.file is None else self.file.url,
            None if self.file is None else self.file.name,
            None if self.file is None else self.file.size,
            None if self.file is None else self.file.dimensions,
            None if self.poster is None else self.poster.id,
            None if self.poster is None else self.poster.flag
        ]
        for field in fields:
            yield field

    def __copy__(self):
        return Post(
            self.thread,
            self.number,
            self.timestamp,
            self.text,
            is_original_post=self.is_original_post,
            file=self.file,
            poster=self.poster
        )

    def __deepcopy__(self, memo: dict[Any, Any]):
        return Post(
            copy.deepcopy(self.thread, memo),
            self.number,
            copy.deepcopy(self.timestamp, memo),
            copy.deepcopy(self.text, memo),
            is_original_post=self.is_original_post,
            file=copy.deepcopy(self.file, memo),
            poster=copy.deepcopy(self.poster, memo)
        )
