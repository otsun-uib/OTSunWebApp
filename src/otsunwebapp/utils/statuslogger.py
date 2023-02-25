from __future__ import print_function

import os
import json
import logging

logger = logging.getLogger(__name__)


class StatusLogger(object):
    """
    StatusLogger keeps information about the status of a computation.

    Attributes:
        val: current value
        lock: lock for access to data
        total: number of interations to complete the computations
        folder: location where to store the status.log file
        filename: filename where to store information
        data: current status
    """
    def __init__(self, manager, total, folder):
        """
        Inits Status logger with the given parameters
        Args:
            manager: a multiprocessing.Manager object used for locking
            total: the number of iterations to make to complete the process
            folder: the folder where to store the status.log file
        """
        self.val = manager.Value('i', 0)
        self.lock = manager.Lock()
        self.total = total
        self.folder = folder
        self.filename = os.path.join(folder, 'status.json')
        self.data = {'status': 'started', 'percentage': 'N/A'}
        self.save()

    def increment(self):
        """
        Increases self.val value in one unit and updates the status if required
        """
        with self.lock:
            self.val.value += 1
            value = self.val.value
            if (value == self.total) or ((value % (int(self.total / 100)+1)) == 0):
                logger.debug("updating at %d", value)
                self.update()
            else:
                logger.debug("not updating at %d", value)

    def value(self):
        """
        Returns the current value of the counter
        """
        with self.lock:
            return self.val.value

    def update(self):
        """
        Updates the data dictionary and saves the result in the file
        """
        # print("updating data {}".format(self.data_status))
        if self.val.value == self.total:
            status = 'finished'
        else:
            status = 'running'
        percentage = (100*self.val.value)/self.total
        self.data['status'] = status
        self.data['percentage'] = percentage
        self.save()

    def save(self):
        """
        Saves the status data in the self.filename
        """
        logger.info("saving data: %s", self.data)
        with open(self.filename, 'w') as fh:
            json.dump(self.data, fh)


if __name__ == '__main__':
    from multiprocessing import Manager, Pool
    import random
    import time

    logging.basicConfig(level=logging.DEBUG)

    def f(args):
        counter = args[1]
        y = args[0]
        print('Proc {} starts on {}'.format(os.getpid(), y))
        for _ in range(50):
            time.sleep(random.random() / 10.0)
        counter.increment()
        print('Proc {} ends'.format(os.getpid()))
        return args[0] ** 2

    def main():
        manager = Manager()
        counter = StatusLogger(manager, 25, '/tmp')

        pool = Pool(processes=4)

        input_data = [(_, counter) for _ in range(25)]
        counter.total = len(input_data)
        output_data = pool.map(f, input_data)
        print('Count: {}'.format(counter.value()))
        # print(result)
        print(output_data)

    main()
