import serial
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
