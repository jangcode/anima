# -*- coding: utf-8 -*-
# Copyright (c) 2012-2017, Anima Istanbul
#
# This module is part of anima-tools and is released under the BSD 2
# License: http://www.opensource.org/licenses/BSD-2-Clause

from anima import logger
from anima.ui.base import AnimaDialogBase, ui_caller
from anima.ui import IS_PYSIDE, IS_PYSIDE2, IS_PYQT4
from anima.ui.lib import QtCore, QtWidgets, QtGui


if IS_PYSIDE():
    from anima.ui.ui_compiled import time_log_dialog_UI_pyside as time_log_dialog_UI
elif IS_PYSIDE2():
    from anima.ui.ui_compiled import time_log_dialog_UI_pyside2 as time_log_dialog_UI
elif IS_PYQT4():
    from anima.ui.ui_compiled import time_log_dialog_UI_pyqt4 as time_log_dialog_UI
reload(time_log_dialog_UI)


timing_resolution = 10  # in minutes


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

    def __init__(self, parent=None, task=None, timelog=None):
        logger.debug("initializing the interface")
        # store the logged in user
        self.logged_in_user = None
        self.no_time_left = False
        self.extended_hours = None
        self.extended_minutes = None

        self.timelog = timelog
        self.timelog_created = False
        self.task = task

        super(MainDialog, self).__init__(parent)
        self.setupUi(self)

        # customize the ui elements
        from anima.ui.widgets import TaskComboBox
        self.tasks_comboBox = TaskComboBox(self)
        self.tasks_comboBox.setObjectName("tasks_comboBox")
        self.formLayout.setWidget(
            0,
            QtWidgets.QFormLayout.FieldRole,
            self.tasks_comboBox
        )

        # self.start_timeEdit.deleteLater()
        from anima.ui.widgets import TimeEdit
        self.start_timeEdit = TimeEdit(self, resolution=timing_resolution)
        self.start_timeEdit.setCurrentSection(QtWidgets.QDateTimeEdit.MinuteSection)
        self.start_timeEdit.setCalendarPopup(True)
        self.start_timeEdit.setObjectName("start_timeEdit")
        self.start_timeEdit.setWrapping(True)
        self.formLayout.insertRow(4, self.label, self.start_timeEdit)
        self.start_timeEdit.setDisplayFormat("HH:mm")

        # self.end_timeEdit.deleteLater()
        self.end_timeEdit = TimeEdit(self, resolution=timing_resolution)
        self.end_timeEdit.setCurrentSection(QtWidgets.QDateTimeEdit.MinuteSection)
        self.end_timeEdit.setCalendarPopup(True)
        self.end_timeEdit.setObjectName("end_timeEdit")
        self.end_timeEdit.setWrapping(True)
        self.formLayout.insertRow(5, self.label_2, self.end_timeEdit)
        self.end_timeEdit.setDisplayFormat("HH:mm")

        current_time = QtCore.QTime.currentTime()
        # round the minutes to the resolution
        minute = current_time.minute()
        hour = current_time.hour()
        minute = int(minute / float(timing_resolution)) * timing_resolution

        current_time = QtCore.QTime(hour, minute)

        self.start_timeEdit.setTime(current_time)
        self.end_timeEdit.setTime(current_time.addSecs(timing_resolution * 60))

        self.calendarWidget.resource_id = -1

        # setup signals
        self._setup_signals()

        # setup defaults
        self._set_defaults()

        # center window
        self.center_window()

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

        # resource changed
        QtCore.QObject.connect(
            self.resource_comboBox,
            QtCore.SIGNAL('currentIndexChanged(QString)'),
            self.resource_changed
        )

    def _set_defaults(self):
        """sets the defaults for the ui
        """
        logger.debug("started setting up interface defaults")

        # enter revision types
        revision_types = [
            'Yetistiremedim',
            'Ajans',
            'Yonetmen',
            'Ic Revizyon',
        ]

        self.revision_type_comboBox.addItems(revision_types)

        if not self.logged_in_user:
            self.logged_in_user = self.get_logged_in_user()

        # fill the tasks comboBox
        from stalker import Status, Task
        status_wfd = Status.query.filter(Status.code == 'WFD').first()
        status_cmpl = Status.query.filter(Status.code == 'CMPL').first()
        status_prev = Status.query.filter(Status.code == 'PREV').first()

        if not self.timelog:
            # dialog is in create TimeLog mode
            # if a task has been given just feed that task to the comboBox
            if self.task:
                all_tasks = [self.task]
            else:
                # no Task is given nor updating a TimeLog
                # show all the suitable tasks of the logged_in_user
                all_tasks = Task.query \
                    .filter(Task.resources.contains(self.logged_in_user)) \
                    .filter(Task.status != status_wfd) \
                    .filter(Task.status != status_cmpl) \
                    .filter(Task.status != status_prev) \
                    .all()
                # sort the task labels
                all_tasks = sorted(
                    all_tasks,
                    key=lambda task:
                    '%s | %s' % (
                        task.project.name.lower(),
                        ' | '.join(map(lambda x: x.name.lower(), task.parents))
                    )
                )
        else:
            # dialog is working in update TimeLog mode
            all_tasks = [self.timelog.task]

        self.tasks_comboBox.setSizeAdjustPolicy(
            QtWidgets.QComboBox.AdjustToContentsOnFirstShow
        )
        self.tasks_comboBox.setFixedWidth(360)
        self.tasks_comboBox.clear()
        self.tasks_comboBox.addTasks(all_tasks)

        self.tasks_comboBox.setSizePolicy(
            QtWidgets.QSizePolicy.MinimumExpanding,
            QtWidgets.QSizePolicy.Minimum
        )

        # if a time log is given set the fields from the given time log
        if self.timelog:
            # first update Task
            try:
                self.tasks_comboBox.setCurrentTask(self.timelog.task)
            except IndexError as e:
                return

            # set the resource

            # and disable the tasks_comboBox and resource_comboBox
            self.tasks_comboBox.setEnabled(False)
            self.resource_comboBox.setEnabled(False)

            # set the start and end time
            from anima.utils import utc_to_local
            start_date = utc_to_local(self.timelog.start)
            end_date = utc_to_local(self.timelog.end)

            # set the date
            self.calendarWidget.setSelectedDate(
                QtCore.QDate(start_date.year, start_date.month, start_date.day)
            )

            # first reset the start and end time values
            self.start_timeEdit.setTime(QtCore.QTime(0, 0))
            self.end_timeEdit.setTime(QtCore.QTime(23, 50))

            # now set the timelog time
            self.start_timeEdit.setTime(
                QtCore.QTime(
                    start_date.hour,
                    start_date.minute
                )
            )
            self.end_timeEdit.setTime(
                QtCore.QTime(
                    end_date.hour,
                    end_date.minute
                )
            )

        self.fill_calendar_with_time_logs()

    def fill_calendar_with_time_logs(self):
        """fill the calendar with daily time log info
        """
        resource_id = self.get_current_resource_id()
        # do not update if the calendar is showing the same user
        if self.calendarWidget.resource_id == resource_id or resource_id == -1:
            return

        tool_tip_text_format = u'{start:%H:%M} - {end:%H:%M} | {task_name}'

        # import time
        # start = time.time()
        # get all the TimeLogs grouped daily
        sql = """-- TOP DOWN SEARCH --
select
    "TimeLogs".start::date as date,
    array_agg(task_rec_data.full_path) as task_name,
    array_agg("TimeLogs".start) as start,
    array_agg("TimeLogs".end) as end,
    sum(extract(epoch from ("TimeLogs".end - "TimeLogs".start)))

from "TimeLogs"

join (
    with recursive recursive_task(id, parent_id, path_names) as (
        select
        task.id,
        task.project_id,
        -- task.project_id::text as path,
        ("Projects".code || '') as path_names
        from "Tasks" as task
        join "Projects" on task.project_id = "Projects".id
        where task.parent_id is NULL
    union all
        select
        task.id,
        task.parent_id,
        -- (parent.path || '|' || task.parent_id:: text) as path,
        (parent.path_names || ' | ' || "Parent_SimpleEntities".name) as path_names
        from "Tasks" as task
        inner join recursive_task as parent on task.parent_id = parent.id
        inner join "SimpleEntities" as "Parent_SimpleEntities" on parent.id = "Parent_SimpleEntities".id
    ) select
        recursive_task.id,
        "SimpleEntities".name || ' (' || recursive_task.path_names || ')' as full_path
    from recursive_task
    join "SimpleEntities" on recursive_task.id = "SimpleEntities".id
) as task_rec_data on "TimeLogs".task_id = task_rec_data.id

-- getting all the data is as fast as getting one, so get all the TimeLogs of this user
where "TimeLogs".resource_id = :resource_id
group by cast("TimeLogs".start as date)
order by cast("TimeLogs".start as date)
        """
        from sqlalchemy import text
        from stalker.db.session import DBSession
        result = DBSession.connection().execute(
            text(sql),
            resource_id=resource_id
        ).fetchall()
        # end = time.time()
        # print('getting data from sql: %0.3f sec' % (end - start))

        from anima.utils import utc_to_local
        time_shifter = utc_to_local
        import stalker
        if int(stalker.__version__.replace('.', '')) >= 218:
            def time_shifter(x):
                return x

        for r in result:
            calendar_day = r[0]
            year = calendar_day.year
            month = calendar_day.month
            day = calendar_day.day
            daily_logged_seconds = r[4]
            daily_logged_hours = daily_logged_seconds // 3600
            daily_logged_minutes = \
                (daily_logged_seconds - daily_logged_hours * 3600) // 60

            tool_tip_text_data = [
                u'Total: %i h %i min logged' %
                (daily_logged_hours, daily_logged_minutes)
                if daily_logged_hours
                else u'Total: %i min logged' % daily_logged_minutes
            ]
            for task_name, start, end in sorted(
                    zip(r[1], r[2], r[3]), key=lambda x: x[1]):
                time_log_tool_tip_text = tool_tip_text_format.format(
                    start=time_shifter(start),
                    end=time_shifter(end),
                    task_name=task_name
                )
                tool_tip_text_data.append(time_log_tool_tip_text)

            merged_tool_tip = u'\n'.join(tool_tip_text_data)

            date_format = QtGui.QTextCharFormat()
            bg_brush = QtGui.QBrush()
            bg_brush.setColor(
                QtGui.QColor(0, 255.0 / 86400.0 * daily_logged_seconds, 0)
            )

            date_format.setBackground(bg_brush)
            date_format.setToolTip(merged_tool_tip)

            date = QtCore.QDate(year, month, day)

            self.calendarWidget.setDateTextFormat(date, date_format)

    def tasks_combo_box_index_changed(self, task_label):
        """runs when another task has been selected
        """
        # task = self.get_current_task()
        task = self.tasks_comboBox.currentTask()
        self.update_percentage()
        self.update_info_text()

        # update resources comboBox
        resource_names = []
        if self.logged_in_user in task.resources:
            resource_names = [self.logged_in_user.name]

        for r in task.resources:
            if r != self.logged_in_user:
                resource_names.append(r.name)

        self.resource_comboBox.clear()
        self.resource_comboBox.addItems(resource_names)

    def get_current_resource(self):
        """returns the current resource
        """
        resource_name = self.resource_comboBox.currentText()
        from stalker import User
        return User.query.filter(User.name == resource_name).first()

    def get_current_resource_id(self):
        """returns the current resource
        """
        resource_name = self.resource_comboBox.currentText()
        from stalker import User
        from stalker.db.session import DBSession
        return DBSession.query(User.id)\
            .filter(User.name == resource_name)\
            .first()

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

    def resource_changed(self, resource_name):
        """runs when the selected resource has changed
        """
        self.fill_calendar_with_time_logs()

    def calculate_percentage(self):
        # task = self.get_current_task()
        task = self.tasks_comboBox.currentTask()
        schedule_seconds = task.schedule_seconds
        logged_seconds = task.total_logged_seconds
        start_time = self.start_timeEdit.time()
        end_time = self.end_timeEdit.time()
        time_log_seconds = start_time.secsTo(end_time)
        percentage = \
            (logged_seconds + time_log_seconds) / float(schedule_seconds) * 100
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
        # task = self.get_current_task()
        task = self.tasks_comboBox.currentTask()
        schedule_seconds = task.schedule_seconds
        logged_seconds = task.total_logged_seconds
        start_time = self.start_timeEdit.time()
        end_time = self.end_timeEdit.time()
        time_log_seconds = start_time.secsTo(end_time)

        remaining_seconds = \
            schedule_seconds - (logged_seconds + time_log_seconds)

        # if a time log given add its seconds
        if self.timelog:
            remaining_seconds += self.timelog.total_seconds

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

    def accept(self):
        """overridden accept method
        """
        # get the info
        task = self.tasks_comboBox.currentTask()
        resource = self.get_current_resource()

        # war the user if the resource is not the logged_in_user
        if resource != self.logged_in_user:
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setWindowTitle('Baskasi Adina TimeLog Giriyorsun')
            msg_box.setText('Baskasi adina TimeLog giriyorsun???')
            accept_button = msg_box.addButton(
                'Sorumlulugu Kabul Ediyorum',
                QtWidgets.QMessageBox.AcceptRole
            )
            cancel_button = msg_box.addButton(
                'Cancel',
                QtWidgets.QMessageBox.RejectRole
            )
            msg_box.setDefaultButton(cancel_button)
            msg_box.exec_()
            clicked_button = msg_box.clickedButton()
            if clicked_button == cancel_button:
                return

        description = self.description_plainTextEdit.toPlainText()
        revision_cause_text = \
            self.revision_type_comboBox.currentText().replace(' ', '_')

        is_complete = self.set_as_complete_radioButton.isChecked()
        submit_to_final_review = \
            self.submit_for_final_review_radioButton.isChecked()

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

        today_midnight = datetime.datetime.now().replace(
            hour=23, minute=59, second=59, microsecond=999
        )

        # raise an error if the user is trying to enter a TimeLog to the future
        if start_date > today_midnight or end_date > today_midnight:
            QtWidgets.QMessageBox.critical(
                self,
                'Error',
                'Gelecege TimeLog giremezsiniz!!!',
            )
            return

        # convert them to utc
        from anima.utils import local_to_utc
        utc_start_date = local_to_utc(start_date)
        utc_end_date = local_to_utc(end_date)

        # create a TimeLog
        # print('Task          : %s' % task.name)
        # print('Resource      : %s' % resource.name)
        # print('utc_start_date: %s' % utc_start_date)
        # print('utc_end_date  : %s' % utc_end_date)

        # now if we are not using extra time just create the TimeLog
        from stalker import TimeLog
        from stalker.db.session import DBSession
        from stalker.exceptions import OverBookedError
        utc_now = local_to_utc(datetime.datetime.now())

        import stalker
        from distutils.version import LooseVersion
        if LooseVersion(stalker.__version__) >= LooseVersion('0.2.18'):
            # inject timezone info
            import pytz
            utc_start_date = utc_start_date.replace(tzinfo=pytz.utc)
            utc_end_date = utc_end_date.replace(tzinfo=pytz.utc)
            utc_now = utc_now.replace(tzinfo=pytz.utc)

        from sqlalchemy.exc import IntegrityError
        if not self.timelog:
            try:
                new_time_log = TimeLog(
                    task=task,
                    resource=resource,
                    start=utc_start_date,
                    end=utc_end_date,
                    description=description,
                    date_created=utc_now
                )
            except OverBookedError:
                # inform the user that it can not do that
                QtWidgets.QMessageBox.critical(
                    self,
                    'Error',
                    'O saatte baska time log var!!!'
                )
                DBSession.rollback()
                return

            try:
                DBSession.add(new_time_log)
                DBSession.commit()
                self.timelog_created = True
            except IntegrityError as e:
                DBSession.rollback()
                QtWidgets.QMessageBox.critical(
                    self,
                    'Error',
                    'Database hatasi!!!'
                    '<br>'
                    '%s' % e
                )
                return
        else:
            # just update the date values
            self.timelog.start = utc_start_date
            self.timelog.end = utc_end_date
            self.timelog.date_updated = utc_now
            DBSession.add(self.timelog)
            DBSession.commit()

        if self.no_time_left:
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
                type=revision_type,
                created_by=self.logged_in_user,
                date_created=utc_now
            )
            DBSession.add(new_note)
            task.notes.append(new_note)

            try:
                DBSession.commit()
            except IntegrityError as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    'Error',
                    'Database hatasi!!!'
                    '<br>'
                    '%s' % e
                )
                DBSession.rollback()
                return

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
                type=forced_status_type,
                created_by=self.logged_in_user,
                date_created=utc_now
            )
            DBSession.add(new_note)
            task.notes.append(new_note)
            task.status = status_cmpl
            DBSession.commit()

        elif submit_to_final_review:
            # clip the Task timing to current time logs
            from stalker import Task
            schedule_timing, schedule_unit = \
                task.least_meaningful_time_unit(
                    task.total_logged_seconds
                )

            task.schedule_timing = schedule_timing
            task.schedule_unit = schedule_unit
            DBSession.add(task)

            try:
                DBSession.commit()
            except IntegrityError as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    'Error',
                    'Database hatasi!!!'
                    '<br>'
                    '%s' % e
                )
                DBSession.rollback()
                return

            # request a review
            reviews = task.request_review()
            for review in reviews:
                review.created_by = review.updated_by = self.logged_in_user
                review.date_created = utc_now
                review.date_updated = utc_now
            DBSession.add_all(reviews)

            # and create a Note for the Task
            request_review_note_type = \
                Type.query\
                    .filter(Type.target_entity_type == 'Note')\
                    .filter(Type.name == 'Request Review')\
                    .first()

            from stalker import Note
            request_review_note = Note(
                type=request_review_note_type,
                created_by=self.logged_in_user,
                date_created=utc_now
            )
            DBSession.add(request_review_note)
            DBSession.add(task)
            task.notes.append(request_review_note)

            try:
                DBSession.commit()
            except IntegrityError as e:
                DBSession.rollback()
                QtWidgets.QMessageBox.critical(
                    self,
                    'Error',
                    'Database hatasi!!!'
                    '<br>'
                    '%s' % e
                )
                return

        # # Fix statuses
        # task.update_parent_statuses()
        # for dep_task in task.dependent_of:
        #     dep_task.update_status_with_dependent_statuses()
        fix_task_statuses(task)
        try:
            DBSession.commit()
        except IntegrityError as e:
            DBSession.rollback()
            QtWidgets.QMessageBox.critical(
                self,
                'Error',
                'Database hatasi!!!'
                '<br>'
                '%s' % e
            )
            return

        # if nothing bad happens close the dialog
        super(MainDialog, self).accept()


# The following functions are coming from Stalker Pyramid
def check_task_status_by_schedule_model(task):
    """after scheduling project checks the task statuses
    """
    logger.debug('check_task_status_by_schedule_model starts')

    from stalker import Status
    status_cmpl = Status.query.filter(Status.code == 'CMPL').first()
    if task.is_leaf and task.schedule_model == 'duration':
        depends_tasks_cmpl = True
        for dependent_task in task.depends:
            if dependent_task.status is not status_cmpl:
                depends_tasks_cmpl = False

        if depends_tasks_cmpl:
            task.status = status_cmpl


def fix_task_statuses(task):
    """fixes task statuses
    """
    from stalker import Task
    if task:
        assert isinstance(task, Task)
        task.update_status_with_dependent_statuses()
        task.update_status_with_children_statuses()
        task.update_schedule_info()

        check_task_status_by_schedule_model(task)
        fix_task_computed_time(task)


def fix_task_computed_time(task):
    """Fix task's computed_start and computed_end time based on timelogs of the given task.

    :param task: The stalker task instance that the time log will be
      investigated.
    :type task: :class:`stalker.models.task.Task`
    :return: :class:`datetime.datetime`
    """
    if task.status.code not in ['CMPL', 'STOP', 'OH']:
        return

    else:
        start_time = get_actual_start_time(task)
        end_time = get_actual_end_time(task)

        task.computed_start = start_time
        task.computed_end = end_time

        logger.debug('Task computed time is fixed!')


def get_actual_start_time(task):
    """Returns the start time of the earliest time logs of the given task if it
    has any time logs, or it will return the task start_time.

    :param task: The stalker task instance that the time log will be
      investigated.
    :type task: :class:`stalker.models.task.Task`
    :return: :class:`datetime.datetime`
    """
    from stalker import Task, TimeLog

    if not isinstance(task, Task):
        raise TypeError(
            'task should be an instance of stalker.models.task.Task, not %s' %
            task.__class__.__name__
        )

    first_time_log = TimeLog.query\
        .filter(TimeLog.task == task)\
        .order_by(TimeLog.start.asc())\
        .first()

    if first_time_log:
        return first_time_log.start
    else:
        if task.schedule_model == 'duration':
            start_time = task.project.start
            for tdep in task.depends:
                if tdep.computed_end > start_time:
                    start_time = tdep.computed_end
            return start_time

    return task.computed_start


def get_actual_end_time(task):
    """Returns the end time of the latest time logs of the given task if it
    has any time logs, or it will return the task end_time.

    :param task: The stalker task instance that the time log will be
      investigated.
    :type task: :class:`stalker.models.task.Task`
    :return: :class:`datetime.datetime`
    """
    from stalker import Task, TimeLog

    if not isinstance(task, Task):
        raise TypeError(
            'task should be an instance of stalker.models.task.Task, not %s' %
            task.__class__.__name__
        )

    end_time_log = TimeLog.query\
        .filter(TimeLog.task == task)\
        .order_by(TimeLog.end.desc())\
        .first()

    if end_time_log:
        return end_time_log.end
    else:
        if task.schedule_model == 'duration':
            end_time = task.project.start
            import datetime
            for tdep in task.depends:
                if tdep.computed_end > end_time:
                    duration = datetime.timedelta(minutes=0)
                    if task.schedule_unit == 'min':
                        duration = \
                            datetime.timedelta(minutes=task.schedule_timing)
                    elif task.schedule_unit == 'h':
                        duration = \
                             datetime.timedelta(hours=task.schedule_timing)
                    elif task.schedule_unit == 'd':
                        duration = \
                            datetime.timedelta(days=task.schedule_timing)
                    elif task.schedule_unit == 'w':
                        duration = \
                            datetime.timedelta(weeks=task.schedule_timing)
                    elif task.schedule_unit == 'm':
                        duration = \
                            datetime.timedelta(weeks=4*task.schedule_timing)
                    end_time = tdep.computed_end + duration
            return end_time

    return task.computed_end
