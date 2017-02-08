# -*- coding: utf-8 -*-
# Copyright (c) 2012-2015, Anima Istanbul
#
# This module is part of anima-tools and is released under the BSD 2
# License: http://www.opensource.org/licenses/BSD-2-Clause

from anima import logger
from anima.ui.base import AnimaDialogBase, ui_caller
from anima.ui import IS_PYSIDE, IS_PYSIDE2, IS_PYQT4
from anima.ui.lib import QtCore, QtWidgets


if IS_PYSIDE():
    from anima.ui.ui_compiled import time_log_dialog_UI_pyside as time_log_dialog_UI
elif IS_PYSIDE2():
    from anima.ui.ui_compiled import time_log_dialog_UI_pyside2 as time_log_dialog_UI
elif IS_PYQT4():
    from anima.ui.ui_compiled import time_log_dialog_UI_pyqt4 as time_log_dialog_UI
reload(time_log_dialog_UI)


timing_resolution = 10  # in minutes


class TimeEdit(QtWidgets.QTimeEdit):
    """Customized time edit widget
    """

    def __init__(self, *args, **kwargs):
        self.resolution = None
        if 'resolution' in kwargs:
            self.resolution = kwargs['resolution']
            kwargs.pop('resolution')

        super(TimeEdit, self).__init__(*args, **kwargs)

    def stepBy(self, step):
        """Custom stepBy function

        :param step:
        :return:
        """
        if self.currentSectionIndex() == 1:
            if step < 0:
                step = -self.resolution
            else:
                step = self.resolution
        super(TimeEdit, self).stepBy(step)


def UI(app_in=None, executor=None, **kwargs):
    """
    :param app_in: A Qt Application instance, which you can pass to let the UI
      be attached to the given applications event process.

    :param executor: Instead of calling app.exec_ the UI will call this given
      function. It also passes the created app instance to this executor.

    """
    return ui_caller(app_in, executor, MainDialog, **kwargs)


class MainDialog(QtWidgets.QDialog, time_log_dialog_UI.Ui_Dialog, AnimaDialogBase):
    """The TimeLog Dialog
    """

    def __init__(self, parent=None, task=None):
        logger.debug("initializing the interface")
        # store the logged in user
        self.logged_in_user = None
        self.no_time_left = False
        self.extended_hours = None
        self.extended_minutes = None

        self.timelog_created = False

        super(MainDialog, self).__init__(parent)
        self.setupUi(self)

        # customize the ui elements
        self.start_timeEdit.deleteLater()
        self.start_timeEdit = TimeEdit(self, resolution=timing_resolution)
        self.start_timeEdit.setCurrentSection(QtWidgets.QDateTimeEdit.MinuteSection)
        self.start_timeEdit.setCalendarPopup(True)
        self.start_timeEdit.setObjectName("start_timeEdit")
        self.start_timeEdit.setWrapping(True)
        self.formLayout.insertRow(4, self.label, self.start_timeEdit)
        self.start_timeEdit.setDisplayFormat("HH:mm")

        self.end_timeEdit.deleteLater()
        self.end_timeEdit = TimeEdit(self, resolution=timing_resolution)
        self.end_timeEdit.setCurrentSection(QtWidgets.QDateTimeEdit.MinuteSection)
        self.end_timeEdit.setCalendarPopup(True)
        self.end_timeEdit.setObjectName("end_timeEdit")
        self.end_timeEdit.setWrapping(True)
        self.formLayout.insertRow(5, self.label_2, self.end_timeEdit)
        self.end_timeEdit.setDisplayFormat("HH:mm")

        # disable request revision for now
        self.submit_for_final_review_radioButton.setEnabled(False)

        current_time = QtCore.QTime.currentTime()
        # round the minutes to the resolution
        minute = current_time.minute()
        hour = current_time.hour()
        minute = int(minute / float(timing_resolution)) * timing_resolution

        current_time = QtCore.QTime(hour, minute)

        self.start_timeEdit.setTime(current_time)
        self.end_timeEdit.setTime(current_time.addSecs(timing_resolution * 60))

        # setup signals
        self._setup_signals()

        # setup defaults
        self._set_defaults()

        # center window
        self.center_window()

        # if given a task set it in to the view
        self.set_current_task(task)

    def close(self):
        logger.debug('closing the ui')
        QtWidgets.QDialog.close(self)

    def show(self):
        """overridden show method
        """
        logger.debug('MainDialog.show is started')
        self.logged_in_user = self.get_logged_in_user()
        if not self.logged_in_user:
            self.close()
            return_val = None
        else:
            return_val = super(MainDialog, self).show()

        logger.debug('MainDialog.show is finished')
        return return_val

    def _setup_signals(self):
        """sets up the signals
        """
        logger.debug("start setting up interface signals")

        # tasks_comboBox
        QtCore.QObject.connect(
            self.tasks_comboBox,
            QtCore.SIGNAL('currentIndexChanged(QString)'),
            self.tasks_combo_box_index_changed
        )

        # start_timeEdit
        QtCore.QObject.connect(
            self.start_timeEdit,
            QtCore.SIGNAL('timeChanged(QTime)'),
            self.start_time_changed
        )

        # end_timeEdit
        QtCore.QObject.connect(
            self.end_timeEdit,
            QtCore.SIGNAL('timeChanged(QTime)'),
            self.end_time_changed
        )

    def _set_defaults(self):
        """sets up the defaults for the interface
        """
        logger.debug("started setting up interface defaults")

        # enter revision types
        revision_types = [
            'Ajans',
            'Yonetmen',
            'Ic_Revizyon',
            'Yetistiremedim'
        ]

        self.revision_type_comboBox.addItems(revision_types)

        if not self.logged_in_user:
            self.logged_in_user = self.get_logged_in_user()

        # fill the tasks comboBox
        from stalker import Status, Task
        status_wfd = Status.query.filter(Status.code == 'WFD').first()
        status_cmpl = Status.query.filter(Status.code == 'CMPL').first()

        all_tasks = Task.query\
            .filter(Task.resources.contains(self.logged_in_user))\
            .filter(Task.status != status_wfd)\
            .filter(Task.status != status_cmpl)\
            .all()

        # TODO: Please use a custom ComboBox that can hold tasks in it
        # prepare task labels
        task_labels = []
        for task in all_tasks:
            # this is dirty
            task_label = '%s (%s) - %s' % (
                task.name,
                '%s | %s' % (
                    task.project.name,
                    ' | '.join(map(lambda x: x.name, task.parents))
                ),
                task.id
            )
            task_labels.append(task_label)

        # sort the task labels
        task_labels = sorted(task_labels, key=lambda x: x.split('(')[1])

        self.tasks_comboBox.addItems(task_labels)

    def tasks_combo_box_index_changed(self, task_label):
        """runs when another task has been selected
        """
        task = self.get_current_task()
        self.update_percentage()
        self.update_info_text()

        # update resources comboBox
        resource_names = [self.logged_in_user.name]
        for r in task.resources:
            if r != self.logged_in_user:
                resource_names.append(r.name)

        self.resource_comboBox.clear()
        self.resource_comboBox.addItems(resource_names)

    def get_current_task(self):
        """returns the current task
        """
        # try to get the task
        task_label = self.tasks_comboBox.currentText()
        task_id = task_label.split(' - ')[1]
        # first update the completeness value
        from stalker import Task
        task = Task.query.get(task_id)
        return task

    def set_current_task(self, task):
        """sets the current task
        """
        # print('setting current task to: %s' % task)
        if not task:
            return

        task_id = task.id
        index = self.tasks_comboBox.findText(
            ' - %i' % task_id, QtCore.Qt.MatchEndsWith
        )

        # print ('index: %s' % index)
        if index != -1:
            self.tasks_comboBox.setCurrentIndex(index)

    def get_current_resource(self):
        """returns the current resource
        """
        resource_name = self.resource_comboBox.currentText()
        from stalker import User
        return User.query.filter(User.name == resource_name).first()

    def start_time_changed(self, q_time):
        """validates the start time
        """
        end_time = self.end_timeEdit.time()
        if q_time >= end_time:
            self.end_timeEdit.setTime(q_time.addSecs(timing_resolution * 60))
        self.update_percentage()
        self.update_info_text()

    def end_time_changed(self, q_time):
        """validates the end time
        """
        start_time = self.start_timeEdit.time()
        if q_time <= start_time:
            if q_time.hour() == 0 and q_time.minute() == 0:
                start_time = q_time
                end_time = q_time.addSecs(timing_resolution * 60)
                self.end_timeEdit.setTime(end_time)
            else:
                start_time = q_time.addSecs(-timing_resolution * 60)
            self.start_timeEdit.setTime(start_time)

        self.update_percentage()
        self.update_info_text()

    def calculate_percentage(self):
        task = self.get_current_task()
        schedule_seconds = task.schedule_seconds
        logged_seconds = task.total_logged_seconds
        start_time = self.start_timeEdit.time()
        end_time = self.end_timeEdit.time()
        time_log_seconds = start_time.secsTo(end_time)
        percentage = (logged_seconds + time_log_seconds) / \
                     float(schedule_seconds) * 100
        return percentage

    def update_percentage(self):
        """updates the percentage
        """
        percentage = self.calculate_percentage()
        self.task_progressBar.setMinimum(0)
        self.task_progressBar.setMaximum(100)
        self.task_progressBar.setValue(percentage)

    def update_info_text(self):
        """updated the info text
        """
        task = self.get_current_task()
        schedule_seconds = task.schedule_seconds
        logged_seconds = task.total_logged_seconds
        start_time = self.start_timeEdit.time()
        end_time = self.end_timeEdit.time()
        time_log_seconds = start_time.secsTo(end_time)

        remaining_seconds = \
            schedule_seconds - (logged_seconds + time_log_seconds)

        # calculate the remaining minutes and hours
        self.no_time_left = False
        if remaining_seconds < 0:
            self.no_time_left = True
            remaining_seconds = abs(remaining_seconds)

        hours = remaining_seconds // 3600
        minutes = (remaining_seconds - hours * 3600) // 60
        if self.no_time_left:
            self.info_area_label.setText(
                'You need <b>%i h %i min</b> extra time. '
                'If you enter this time log, time of the task will be '
                'extended. Are you sure?' % (hours, minutes)
            )
            self.show_revision_fields()
            self.extended_hours = hours
            self.extended_minutes = minutes
        else:
            self.hide_revision_fields()
            self.info_area_label.setText(
                'If you enter this time log, '
                '<b>%i h %i min</b> will remain to complete this task.' %
                (hours, minutes)
            )
            self.extended_hours = None
            self.extended_minutes = None

    def show_revision_fields(self):
        """shows the revision fields
        """
        self.revision_label.show()
        self.revision_type_comboBox.show()

    def hide_revision_fields(self):
        """hides the revision fields
        """
        self.revision_label.hide()
        self.revision_type_comboBox.hide()

    def utc_to_local(self, utc_dt):
        """converts the given UTC time to local time
        """
        import calendar
        import datetime
        timestamp = calendar.timegm(utc_dt.timetuple())
        local_dt = datetime.datetime.fromtimestamp(timestamp)
        assert utc_dt.resolution >= datetime.timedelta(microseconds=1)
        return local_dt.replace(microsecond=utc_dt.microsecond)

    def local_to_utc(self, local_dt):
        """converts the given local time to UTC time
        """
        return local_dt - (self.utc_to_local(local_dt) - local_dt)

    def accept(self):
        """overridden accept method
        """
        # get the info
        task = self.get_current_task()
        resource = self.get_current_resource()
        description = self.description_plainTextEdit.toPlainText()
        revision_cause_text = self.revision_type_comboBox.currentText()

        is_complete = self.set_as_complete_radioButton.isChecked()

        # get the revision Types
        from stalker import Type
        revision_type = Type.query\
            .filter(Type.target_entity_type == 'Note')\
            .filter(Type.name == revision_cause_text)\
            .first()

        date = self.calendarWidget.selectedDate()
        start = self.start_timeEdit.time()
        end = self.end_timeEdit.time()

        # construct proper datetime.DateTime instances
        import datetime
        start_date = datetime.datetime(
            date.year(), date.month(), date.day(),
            start.hour(), start.minute()
        )
        end_date = datetime.datetime(
            date.year(), date.month(), date.day(),
            end.hour(), end.minute()
        )

        # convert them to utc
        utc_start_date = self.local_to_utc(start_date)
        utc_end_date = self.local_to_utc(end_date)

        # create a TimeLog
        # print('Task          : %s' % task.name)
        # print('Resource      : %s' % resource.name)
        # print('utc_start_date: %s' % utc_start_date)
        # print('utc_end_date  : %s' % utc_end_date)

        # now if we are not using extra time just create the TimeLog
        from stalker import db, TimeLog
        from stalker.exceptions import OverBookedError
        try:
            new_time_log = TimeLog(
                task=task,
                resource=resource,
                start=utc_start_date,
                end=utc_end_date,
                description=description
            )
        except OverBookedError as e:
            # inform the user that it can not do that
            QtWidgets.QMessageBox.critical(
                self,
                'Error',
                'O saatte baska time log var!!!'
            )
            return

        from sqlalchemy.exc import IntegrityError
        try:
            db.DBSession.add(new_time_log)
            db.DBSession.commit()
            self.timelog_created = True
        except IntegrityError as e:
            QtWidgets.QMessageBox.critical(
                self,
                'Error',
                'Database hatasi!!!'
            )
            db.DBSession.rollback()
            return

        if not self.no_time_left:
            # we have no time left so automatically extend the task
            from stalker import Task
            schedule_timing, schedule_unit = \
                task.least_meaningful_time_unit(
                    task.total_logged_seconds
                )

            if schedule_timing != 0:
                task.schedule_timing = schedule_timing
                task.schedule_unit = schedule_unit

            # also create a Note
            from stalker import Note
            new_note = Note(
                content='Extending timing of the task <b>%s h %s min.</b>' % (
                    self.extended_hours,
                    self.extended_minutes
                ),
                type=revision_type
            )
            db.DBSession.add(new_note)
            task.notes.append(new_note)

            db.DBSession.commit()

        if is_complete:
            # set the status to complete
            from stalker import Type, Status
            status_cmpl = Status.query.filter(Status.code == 'CMPL').first()

            forced_status_type = \
                Type.query.filter(Type.name == 'Forced Status').first()

            # also create a Note
            from stalker import Note
            new_note = Note(
                content='%s has changed this task status to Completed' %
                        resource.name,
                type=forced_status_type
            )
            db.DBSession.add(new_note)
            task.notes.append(new_note)
            task.status = status_cmpl
            db.DBSession.commit()

            task.update_parent_statuses()
            db.DBSession.commit()

        # if nothing bad happens close the dialog
        super(MainDialog, self).accept()