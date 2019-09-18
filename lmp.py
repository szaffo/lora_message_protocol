import serial
import textwrap
import time
import threading

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
BIT_PER_SEC = 300
BUFFER_SIZE = 512
PROTOCOL_CODES_NUM = 32
BUNDLE_HEADER_CODE = 2
BASIC_TEXT_CODE = 1
DEVICE_ID = 255

# Logger function
log = print
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
            raise TypeError("Expected {}, but got {}".format(self.type, type(element)))

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
            raise TypeError("Expected {}, but got {}".format(self.type, type(element)))

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
        self._encodedBody = b""

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
        return b"" + self.header.value + self._encodedBody

    @property
    def byteSize(self):
        return len(self.encode("ascii", "replace"))

    @property
    def code(self):
        return self.header.code

    @property
    def length(self):
        return self.header.length

    @property
    def target(self):
        return self.header.target

    @property
    def sender(self):
        return self.header.sender

# <---------------------------------------------------------------------------------->


class Message(Sendable):

    def __init__(self, sender, target, actionCode, message, messageLength=None):
        message = str(message)

        if len(message) > 255:
            raise OversizedMessageError("Message can contain only 255 characters")

        try:
            length = len(message) if messageLength == None else int(messageLength)
        except ValueError as e:
            raise ValueError("Message length must be convertable to int")

        self._header = Header(length, sender, target, actionCode)
        self._body = message
        self._encodedBody = message.encode("ascii", "replace")

    def __repr__(self):
        return self.__class__.__name__ + "(sender={}, target={}, actionCode={}, message=\"{}\")".format(
            self._header.value[1], self._header.value[2], self._header.value[3], self.body
        )

    @property
    def header(self):
        return self._header

    @property
    def body(self):
        # Body stored as string, not bytestring
        return self._body

    @classmethod
    def joinHeaderWithBody(cls, header, body):
        return cls(header.value[1], header.value[2], header.value[3], body, header.value[0])

# <---------------------------------------------------------------------------------->


class BrokenMessage(Message):

    @property
    def brokenLength(self):
        return len(self._body)

    @property
    def body(self):
        return super().body + ("%" * (self.length - self.brokenLength))


# <---------------------------------------------------------------------------------->


class Bundle(Sendable):

    def __init__(self, sender, target, code, message):
        self._data = Queue(Message)

        messages = textwrap.wrap(message, 255)

        if len(messages) > 255:
            raise OversizedMessageError("Bundle can contain only 65025 characters")

        header = Message(sender, target, BUNDLE_HEADER_CODE, len(messages))

        self._data.insert(header)

        for line in messages:
            element = Message(sender, target, code, line)
            self._data.insert(element)

    def __str__(self):
        return "<" + self.__class__.__name__ + " [{}]".format(str(self.header))

    def __repr__(self):
        return self.__class__.__name__ + "(sender={}, target={}, actionCode={}, message=\"{}\")".format(
            self.header.header.value[1], self.header.header.value[2], self.header.header.value[3], self.body
        )

    @property
    def data(self):
        # self._data is queue
        return self._data.data

    @property
    def code(self):
        return self.data[1].code

    @property
    def header(self):
        return self.data[0]

    @property
    def body(self):
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

    @classmethod
    def joinMessages(cls, headerMessage, bodyMessages):
        code = bodyMessages[0].code
        sender = bodyMessages[0].sender
        target = bodyMessages[0].target

        bundle = cls(sender, target, code, bodyMessages[0].body)

        # WARNING This classmethod manipulates the object's private
        # data directly
        [bundle._data.insert(msg) for msg in bodyMessages[1:]]

        return bundle


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
    def length(self):
        return self.value[0]

    @property
    def sender(self):
        return self.value[1]

    @property
    def target(self):
        return self.value[2]

    @property
    def code(self):
        return self.value[3]

    @classmethod
    def unpack(cls, data):
        return cls(data[0], data[1], data[2], data[3])


# <---------------------------------------------------------------------------------->

class Serial(serial.Serial):
    pass

# <---------------------------------------------------------------------------------->


class FlowControlledSerial(Serial):

    def write(self, data):
        counter = 0
        splitted = self.splitByteString(data)

        for current in splitted:
            wTime = len(current) * 8 / BIT_PER_SEC

            counter += super().write(current)

            time.sleep(wTime)

        return counter

    def splitByteString(self, input):
        data = []

        for index in range(0, len(input), BUFFER_SIZE):
            data.append(input[index: index + BUFFER_SIZE])

        return data

# <---------------------------------------------------------------------------------->


class Connection(object):

    def __init__(self, con):

        if not issubclass(type(con), Serial):
            raise NotSerialError("Excepted a Serial object from this library")

        self._serial = con

        self._serialWriteLock = threading.Lock()

        self._slotmanager = SlotManager()

        self._received = TransparentBuffer()

        self.receiverThread = threading.Thread(
            target=self._continousReadGate,
            name="Receiver thread reading from {}".format(self._serial.port),
            daemon=True)

        self.receiverThread.start()

    def _continousReadGate(self):
        try:
            self._continousRead()
        except Exception as e:
            log(e)

    def _continousRead(self):
        while True:
            msg = self._readMessage(1)[0]

            if msg.code == BUNDLE_HEADER_CODE:
                messages = self._readBundleBody(msg)
                # Make bundle from mesages
                sendable = Bundle.joinMessages(msg, messages)
            else:
                sendable = msg

            if (sendable.target == DEVICE_ID) or (sendable.target == 0):
                self._slotmanager(sendable.code, sendable, self)

    def _readBundleBody(self, headerMessage):
        data = self._readMessage(int(headerMessage.body))
        return data

    def _readMessage(self, num):
        messages = []
        while num:
            header = self._readHeader()
            body = self._readBody(header)

            if len(body) < header.length:
                msg = BrokenMessage.joinHeaderWithBody(header, body)
            else:
                msg = Message.joinHeaderWithBody(header, body)

            messages.append(msg)

            num -= 1

        return messages

    def _readHeader(self):
        self._serial.timeout = None
        rawHeader = self._serial.read(4)
        header = Header.unpack(rawHeader)
        return header

    def _readBody(self, header):
        length = header.length
        timeout = (length * 1.5) * 8 / BIT_PER_SEC
        self._serial.timeout = timeout

        rawBody = self._serial.read(length)
        body = rawBody.decode("ascii", "replace")
        return body

    @property
    def slots(self):
        return self._slotmanager

    def send(self, sendable):
        if not issubclass(type(sendable), Sendable):
            raise TypeError("Can send only sendables")

        with self._serialWriteLock:
            self._serial.write(sendable.encode())


    def join(self):
        self.receiverThread.join()


# <---------------------------------------------------------------------------------->


class SlotManager(object):

    def __init__(self):
        self._placeholder = lambda msg: None
        self._slots = [self._placeholder for x in range(255)]

        # Bind underhood functions
        self._slots[1] = _1_BasicText

    def __call__(self, slotnum, arg, connection):
        try:
            if not (slotnum in range(255)):
                raise IndexError("Slots are available from 0-254")

            self._slots[slotnum](arg, connection)
        except Exception as e:
            pass
            # Logging comes here later

    def bind(self, slotnum, func):
        if not (slotnum in range(PROTOCOL_CODES_NUM, 255)):
            raise IndexError(f"Slots are available from {PROTOCOL_CODES_NUM}-254")

        if not callable(func):
            raise TaskNotCallableError()

        if self._slots[slotnum] == self._placeholder:
            self._slots[slotnum] = func
        else:
            raise SlotAlreadyUsedError()

    def unbind(self, slotnum):
        if not (slotnum in range(PROTOCOL_CODES_NUM, 255)):
            raise IndexError(f"Slots are available from {PROTOCOL_CODES_NUM}-254")

        if self._slots[slotnum] == self._placeholder:
            raise EmptySlotError()
        else:
            self._slots[slotnum] = self._placeholder

    def isUsed(self, slotnum):
        if not (slotnum in range(255)):
            raise IndexError("Slots are available from {}-254".format(PROTOCOL_CODES_NUM))

        return not (self._slots[slotnum] == self._placeholder)

    def __str__(self):
        return "<" + self.__class__.__name__ + ">"

    def __repr__(self):
        return self.__class__.__name__ + "()"

# <---------------------------------------------------------------------------------->
# Underhood functions (the first 32 action code)


def _1_BasicText(msg, conn):
    print("Text Received:", msg.body)

# <---------------------------------------------------------------------------------->


def wrapText(text, sender, target):
    # Wrap any string into sendable
    s = Message(sender, target, BASIC_TEXT_CODE, text)\
        if len(text) <= 255 else Bundle(sender, target,  BASIC_TEXT_CODE, text)
    return s


# <---------------------------------------------------------------------------------->

# Exceptions

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

# <---------------------------------------------------------------------------------->


class NotSerialError(Exception):
    pass

# <---------------------------------------------------------------------------------->


class TaskNotCallableError(Exception):
    pass


class SlotAlreadyUsedError(Exception):
    pass


class EmptySlotErro(Exception):
    pass
