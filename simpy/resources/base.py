"""
This module contains the base classes for Simpy's resource system.

:class:`BaseResource` defines the abstract base resource. The request
for putting something into or getting something out of a resource is
modeled as an event that has to be yielded by the requesting process.
:class:`Put` and :class:`Get` are the base event types for this.

.. autoclass:: BaseResource

.. autoclass:: Put
   :members:

.. autoclass:: Get
   :members:

"""
from simpy.core import Event, PENDING


class BaseResource(object):
    """This is the abstract base class for all SimPy resources.

    All resources are bound to a specific
    :class:`~simpy.core.Environment` *env*.

    You can :meth:`put()` something into the resources or :meth:`get()`
    something out of it. Both methods return an event that the
    requesting process has to ``yield``.

    If a put or get operation can be performed immediately (because the
    resource is not full (put) or not empty (get)), that event is
    triggered immediately.

    If a resources is too full or too empty to perform a put or get
    request, the event is pushed to the *put_queue* or *get_queue*. An
    event is popped from one of these queues and triggered as soon as
    the corresponding operation is possible.

    :meth:`put()` and :meth:`get()` only provide the user API and the
    general framework and should not be overridden in subclasses. The
    actual behavior for what happens when a put/get succeeds should
    rather be implemented in :meth:`_do_put()` and :meth:`_do_get()`.

    .. attribute:: PutQueue

        The type to be used for the :attr:`put_queue`. This can either
        be a plain :class:`list` (default) or a subclass of it.
    .. attribute:: GetQueue

        The type to be used for the :attr:`get_queue`. This can either
        be a plain :class:`list` (default) or a sublcass of it.
    .. attribute:: PutEvent

        Event type used for put events. This defaults to ``None`` and
        has to be overridden in sub-classes.

    .. attribute:: GetEvent

        Event type used for get events. This defaults to ``None`` and
        has to be overridden in sub-classes.

    .. attribute:: put_queue

        Queue/list of events waiting to put something into the resource.

    .. attribute:: get_queue

        Queue/list of events waiting to get something out of the
        resource.

    .. automethod:: put
    .. automethod:: get
    .. automethod:: _do_put
    .. automethod:: _do_get

    """

    PutQueue = list
    GetQueue = list
    PutEvent = None
    GetEvent = None

    def __init__(self, env):
        self._env = env
        self.put_queue = self.PutQueue()
        self.get_queue = self.GetQueue()

    def put(self, *args, **kwargs):
        """Try to put something into the resource and return the *put_event*.

        *args* and *kwargs* are passed as arguments to the *put_event*
        when it is created.

        When the *put* request succeeded, check if one or more *get*
        requests from the *get_queue* can now be processed.

        """
        put_event = self.PutEvent(self, *args, **kwargs)

        self._do_put(put_event)
        if put_event._value is not PENDING:
            # The put request has been added to the container and triggered.
            # Check if get requests may now be triggered.
            while self.get_queue:
                get_event = self.get_queue[0]
                self._do_get(get_event)
                if get_event._value is PENDING:
                    break

                self.get_queue.remove(get_event)
        else:
            # The put request has not been added to the container.
            self.put_queue.append(put_event)

        return put_event

    def get(self, *args, **kwargs):
        """Try to get something out of the resource and return the *get_event*.

        *args* and *kwargs* are passed as arguments to the *get_event*
        when it is created.

        When the *get* request succeeded, check if one or more *put*
        requests from the *put_queue* can now be processed.

        """
        get_event = self.GetEvent(self, *args, **kwargs)

        self._do_get(get_event)
        if get_event._value is not PENDING:
            # The get request has been added to the container and triggered.
            # Check if put requests may now be triggered.
            while self.put_queue:
                put_event = self.put_queue[0]
                self._do_put(put_event)
                if put_event._value is PENDING:
                    break

                self.put_queue.remove(put_event)
        else:
            self.get_queue.append(get_event)

        return get_event

    def _do_put(self, event):
        """Actually perform the *put* operation.

        This methods needs to be implemented by subclasses. It receives
        the *put_event* that is created at each request and doesn't
        need to return anything.

        """
        raise NotImplementedError(self)

    def _do_get(self, event):
        """Actually perform the *get* operation.

        This methods needs to be implemented by subclasses. It receives
        the *get_event* that is created at each request and doesn't
        need to return anything.

        """
        raise NotImplementedError(self)


class Put(Event):
    """The base class for all put events.

    It receives the *resource* that created the event.

    This event (and all of its subclasses) can act as context manager
    and can be used with the :keyword:`with` statement to automatically
    cancel a put request if an exception or an
    :class:`simpy.core.Interrupt` occurs:

    .. code-block:: python

        with res.put(item) as request:
            yield request

    It is not used directly by any resource, but rather sub-classed for
    each type.

    """
    def __init__(self, resource):
        super(Put, self).__init__(resource._env)
        self.resource = resource
        self.proc = self.env.active_process

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # If the request has been interrupted, remove it from the queue:
        if self._value is PENDING:
            self.resource.put_queue.remove(self)

    cancel = __exit__
    """Cancel the current put request.

    This method has to be called if a process received an
    :class:`~simpy.core.Interrupt` or an exception while yielding this
    event and is not going to yield this event again.

    If the event was created in a :keyword:`with` statement, this method
    is called automatically.

    """


class Get(Event):
    """The base class for all get events.

    It receives the *resource* that created the event.

    This event (and all of its subclasses) can act as context manager
    and can be used with the :keyword:`with` statement to automatically
    cancel a get request if an exception or an
    :class:`simpy.core.Interrupt` occurs:

    .. code-block:: python

        with res.get() as request:
            yield request

    It is not used directly by any resource, but rather sub-classed for
    each type.

    """
    def __init__(self, resource):
        super(Get, self).__init__(resource._env)
        self.resource = resource
        self.proc = self.env.active_process

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # If the request has been interrupted, remove it from the queue:
        if self.value is PENDING:
            self.resource.get_queue.remove(self)

    cancel = __exit__
    """Cancel the current get request.

    This method has to be called if a process received an
    :class:`~simpy.core.Interrupt` or an exception while yielding this
    event and is not going to yield this event again.

    If the event was created in a :keyword:`with` statement, this method
    is called automatically.

    """
