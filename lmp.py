import serial

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
        return "<Queue of {} with size {}>".format(self.type, self.size)

    def __repr__(self):
        return "Queue(type={}, initData={})".format(self.type, self._data)

    @property
    def size(self):
        return len(self._data)

    @property
    def type(self):
        return self._type

    def insert(self, element):

        if type(element) != self.type:
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


class Buffer(Queue):
    # Buffer only takes Sendable objects or it's children
    pass

# <---------------------------------------------------------------------------------->


class Sendable(object):
    # Connection handler can send only Sendable objects
    # Sendable has no message

    def __init__(self, sender, target, actionCode):
        self._header = Header(0, sender, target, actionCode)

    def __str__(self):
        return "<Sendable [{}]".format(str(self._header))

    def __repr__(self):
        return "Sendable(sender={}, target={}, actionCode={})".format(
            self._header.value[1], self._header.value[2], self._header.value[3]
        )

    @property
    def header(self):
        return self._header


# <---------------------------------------------------------------------------------->


class Message(Sendable):

    def __init__(self, sender, target, actionCode, message):
        if len(message) > 255:
            raise MessageLengthError()

        self._header = Header(len(message), sender, target, actionCode)
        self._body = str(message)

    def __str__(self):
        return "<Message [{}]{}".format(str(self._header), self._body)

    def __repr__(self):
        return "Message(sender={}, target={}, actionCode={}, message=\"{}\")".format(
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
    pass

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
        return "<Header {}>".format(list(self._data))

    def __repr__(self):
        return "Header(length={}, sender={}, target={}, actionCode={})".format(
            self._data[0], self._data[1], self._data[2], self._data[3])

    @property
    def value(self):
        return self._data

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


class MessageLengthError(Exception):
    pass
