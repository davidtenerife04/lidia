import threading

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot


class _Job:
    def __init__(self, fn):
        self.fn = fn
        self.done = threading.Event()
        self.result = None
        self.error = None


class ThreadedController(QObject):
    """Permite usar un PlayerController desde cualquier hilo.

    Debe crearse en el hilo principal (con bucle de eventos). Las llamadas desde otros
    hilos se ejecutan en el hilo principal y bloquean hasta terminar; las excepciones
    se propagan a quien llama.
    """

    _submit = pyqtSignal(object)

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._submit.connect(self._run)

    @pyqtSlot(object)
    def _run(self, job):
        try:
            job.result = job.fn()
        except Exception as e:
            job.error = e
        job.done.set()

    def _call(self, fn):
        if QThread.currentThread() is self.thread():
            return fn()
        job = _Job(fn)
        self._submit.emit(job)
        job.done.wait()
        if job.error is not None:
            raise job.error
        return job.result

    def execute(self, command, args=None):
        return self._call(lambda: self.controller.execute(command, args))

    def snapshot(self):
        return self._call(self.controller.snapshot)
