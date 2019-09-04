import serial
import textwrap

'''
    This protocol can operate with action codes up to 255

    The first 32 is used by the protocol. The others defined by the interfaces.

    First 32 code:
          1 - Basic text
          2 - Bundle header code
          3 - Asking who got the signal
          4 - Answer to asking signal

'''

# <---------------------------------------------------------------------------------->
# Constans
BUNDLE_HEADER_CODE = 2
# <---------------------------------------------------------------------------------->
# Classes


class Queue(object):
    # Basic queue

    def __init__(self, type, initData=None):
        self._type = type
        self._data = []

        if initData != None:
            for element in initData:
                self.insert(element)

    def __str__(self):
        return "<" + self.__class__.__name__ + " of {} with size {}>".format(self.type.__name__, self.size)

    def __repr__(self):
        return self.__class__.__name__ + "(type={}, initData={})".format(self.type.__name__, self._data)

    @property
    def size(self):
        return len(self._data)

    @property
    def type(self):
        return self._type

    @property
    def data(self):
        return self._data.copy()

    def insert(self, element):

        if not issubclass(type(element), self.type):
            raise QueueNonMatchingType("Expected {}, but got {}".format(self.type, type(element)))

        self._data.append(element)

    def peek(self):
        if self.size == 0:
            raise QueueIsEmpty()

        return self._data[0]

    def pop(self):
        if self.size == 0:
            raise QueueIsEmpty()

        element = self._data.pop()

        return element

    def isEmpty(self):
        return self.size == 0

# <---------------------------------------------------------------------------------->


class Dequeue(Queue):
    # It's a double-ended queue
    # It is capable to add element to front of the queue and
    # remove last from queue

    def insertFirst(self, element):
        if not issubclass(type(element), self.type):
            raise QueueNonMatchingType("Expected {}, but got {}".format(self.type, type(element)))

        self._data.insert(0, element)

    def peekLast(self):
        if self.size == 0:
            raise QueueIsEmpty()

        return self._data[self.size - 1]

    def popLast(self):
        if self.size == 0:
            raise QueueIsEmpty()

        element = self._data.pop(self.size - 1)

        return element

# <---------------------------------------------------------------------------------->


class Buffer(Dequeue):
    # Buffer only takes Sendable objects or it's children

    def __init__(self, initData=None):
        super().__init__(Sendable)

        if initData != None:
            for element in initData:
                self.insert(element)

    def __repr__(self):
        return self.__class__.__name__ + "(initData={})".format(self._data)

# <---------------------------------------------------------------------------------->


class TransparentBuffer(Buffer):

    def peekCode(self, code):
        if self.hasCode(code):
            filtered = filter(lambda elem: elem.header.code == code, self.data)
            return next(filtered)

        else:
            raise TransparentBufferNotContainsError()

    def hasCode(self, code):
        filtered = filter(lambda elem: elem.header.code == code, self.data)

        try:
            element = next(filtered)
            return True
        except StopIteration as e:
            return False

    def popCode(self, code):
        if self.hasCode(code):
            element = self._data.pop(self._data.index(self.peekCode(code)))
            return element
        else:
            raise TransparentBufferNotContainsError()

# <---------------------------------------------------------------------------------->


class Sendable(object):
    # Connection handler can send only Sendable objects
    # Sendable has no message

    def __init__(self, sender, target, actionCode):
        self._header = Header(0, sender, target, actionCode)
        self._body = ""

    def __str__(self):
        return "<" + self.__class__.__name__ + " [{}]{}".format(str(self._header), self._body)

    def __repr__(self):
        return self.__class__.__name__ + "(sender={}, target={}, actionCode={})".format(
            self._header.value[1], self._header.value[2], self._header.value[3]
        )

    @property
    def header(self):
        return self._header

    def encode(self):
        return b"" + self.header.value + self.body.encode()

    @property
    def byteSize(self):
        return len(self.encode())

# <---------------------------------------------------------------------------------->

class Message(Sendable):

    def __init__(self, sender, target, actionCode, message):
        message = str(message)

        if len(message) > 255:
            raise OversizedMessageError()

        self._header = Header(len(message), sender, target, actionCode)
        self._body = message

    def __repr__(self):
        return self.__class__.__name__ + "(sender={}, target={}, actionCode={}, message=\"{}\")".format(
            self._header.value[1], self._header.value[2], self._header.value[3], self.body
        )

    @property
    def header(self):
        return self._header

    @property
    def body(self):
        return self._body

# <---------------------------------------------------------------------------------->


class Bundle(Sendable):

    def __init__(self, sender, target, code, message):
        self._data = Queue(Message)

        messages = textwrap.wrap(message, 255)
        if len(messages) > 255:
            raise OversizedMessageError()

        header = Message(sender, target, BUNDLE_HEADER_CODE, len(messages))

        self._data.insert(header)

        for line in messages:
            element = Message(sender, target, code, line)
            self._data.insert(element)

    def __str__(self):
        return "<" + self.__class__.__name__ + " [{}]".format(str(self.header))

    def __repr__(self):
        return self.__class__.__name__ + "(sender={}, target={}, actionCode={}, message=\"{}\")".format(
            self.header.header.value[1], self.header.header.value[2], self.header.header.value[3], self.fullMessage
        )

    @property
    def data(self):
        return self._data.data

    @property
    def header(self):
        return self.data[0]

    @property
    def fullMessage(self):
        string = ""

        for element in self.data[1:]:
            string += element.body
        return string

    @property
    def size(self):
        return len(self.data)

    def encode(self):
        string = b""

        for element in self.data:
            string += element.encode()

        return string


# <---------------------------------------------------------------------------------->


class Header(object):
    # Header of Sendables

    def __init__(self, length, sender, target, actionCode):
        self._data = bytearray(4)

        try:
            self._data[0] = length
            self._data[1] = sender
            self._data[2] = target
            self._data[3] = actionCode
        except TypeError as e:
            raise ValueNotInteger()

        except ValueError as e:
            raise ValueOutOfByteRange()

    def __str__(self):
        return "<" + self.__class__.__name__ + " {}>".format(list(self._data))

    def __repr__(self):
        return self.__class__.__name__ + "(length={}, sender={}, target={}, actionCode={})".format(
            self._data[0], self._data[1], self._data[2], self._data[3])

    @property
    def value(self):
        return self._data

    @property
    def code(self):
        return self.value[3]


# <---------------------------------------------------------------------------------->

# Exceptions


class QueueNonMatchingType(Exception):
    pass


class QueueIsEmpty(Exception):
    pass

# <---------------------------------------------------------------------------------->


class ValueNotInteger(Exception):
    pass


class ValueOutOfByteRange(Exception):
    pass

# <---------------------------------------------------------------------------------->


class OversizedMessageError(Exception):
    pass

# <---------------------------------------------------------------------------------->


class TransparentBufferNotContainsError(Exception):
    pass
