# -*- coding: utf-8 -*-
# Copyright (c) 2012-2017, Anima Istanbul
#
# This module is part of anima-tools and is released under the BSD 2
# License: http://www.opensource.org/licenses/BSD-2-Clause

from anima import logger
from anima.ui.lib import QtCore, QtGui, QtWidgets
from anima.ui.models.task import TaskTreeModel


class TaskTreeView(QtWidgets.QTreeView):
    """A custom tree view to display Tasks info
    """

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('project', None)

        super(TaskTreeView, self).__init__(*args, **kwargs)

        self.is_updating = False

        # delegate = TaskItemDelegate(self)
        # self.setItemDelegate(delegate)
        self.setup_signals()

    def setup_signals(self):
        """connects the signals to slots
        """
        # fit column 0 on expand/collapse
        QtCore.QObject.connect(
            self,
            QtCore.SIGNAL('expanded(QModelIndex)'),
            self.auto_fit_column
        )

        QtCore.QObject.connect(
            self,
            QtCore.SIGNAL('collapsed(QModelIndex)'),
            self.auto_fit_column
        )

        # custom context menu for the tasks_treeView
        self.setContextMenuPolicy(
            QtCore.Qt.CustomContextMenu
        )

        QtCore.QObject.connect(
            self,
            QtCore.SIGNAL("customContextMenuRequested(const QPoint&)"),
            self.show_context_menu
        )

    def replace_with_other(self, layout, index, tree_view=None):
        """Replaces the given tree_view with itself

        :param layout: The QtGui.QLayout of the parent of the original
          QTreeView
        :param index: The item index.
        :param tree_view: The QtWidgets.QTreeView to replace with
        :return:
        """
        if tree_view:
            tree_view.deleteLater()
        layout.insertWidget(index, self)
        return self

    def auto_fit_column(self):
        """fits columns to content
        """
        self.resizeColumnToContents(0)

    def fill(self):
        """fills the tree view with data
        """
        logger.debug('start filling tasks_treeView')
        logger.debug('creating a new model')
        if not self.project:
            from sqlalchemy import alias
            from stalker import Task, Project
            from stalker.db.session import DBSession
            # projects = Project.query.order_by(Project.name).all()
            inner_tasks = alias(Task.__table__)
            subquery = DBSession.query(inner_tasks.c.id).filter(
                inner_tasks.c.project_id == Project.id)
            query = DBSession\
                .query(
                    Project.id, Project.name, Project.entity_type,
                    Project.status_id,
                    subquery.exists().label('has_children')
                )\
                .order_by(Project.name)
            projects = query.all()
        else:
            self.project.has_children = bool(self.project.tasks)
            projects = [self.project]

        logger.debug('projects: %s' % projects)

        task_tree_model = TaskTreeModel()
        task_tree_model.populateTree(projects)
        self.setModel(task_tree_model)
        self.is_updating = False
        logger.debug('finished filling tasks_treeView')

    def show_context_menu(self, position):
        """the custom context menu
        """
        # convert the position to global screen position
        global_position = self.mapToGlobal(position)

        index = self.indexAt(position)
        model = self.model()
        item = model.itemFromIndex(index)
        logger.debug('itemAt(position) : %s' % item)

        if not item:
            return

        if not hasattr(item, 'task'):
            return

        task_id = item.task.id
        if not task_id:
            return

        from stalker import SimpleEntity, Task, Project
        # TODO: Update this to use only task_id
        entity = SimpleEntity.query.get(task_id)
        if not entity:
            return

        # create the menu
        menu = QtWidgets.QMenu()  # Open in browser
        menu.addAction(u'\uf14c Open In Web Browser...')
        menu.addAction(u'\uf0c5 Copy URL')
        menu.addAction(u'\uf0c5 Copy ID to clipboard')

        from anima import defaults
        from stalker import LocalSession
        local_session = LocalSession()
        logged_in_user = local_session.logged_in_user

        if isinstance(entity, Task):
            # this is a task
            task = entity
            from stalker import Status
            status_wfd = Status.query.filter(Status.code == 'WFD').first()
            status_prev = Status.query.filter(Status.code == 'PREV').first()
            status_cmpl = Status.query.filter(Status.code == 'CMPL').first()
            if logged_in_user in task.resources \
                    and task.status not in [status_wfd, status_prev,
                                            status_cmpl]:
                menu.addSeparator()
                menu.addAction(u'\uf073 Create TimeLog...')

            # update task and create child task menu items
            if defaults.is_power_user(logged_in_user):
                menu.addSeparator()
                menu.addAction(u'\uf044 Update Task...')
                menu.addAction(u'\uf0ae Create Child Task...')
                menu.addAction(u'\uf0c5 Duplicate Task Hierarchy...')
                menu.addAction(u'\uf1f8 Delete Task...')

            menu.addSeparator()

            # Add Depends To menu
            depends = task.depends
            if depends:
                depends_to_menu = menu.addMenu(u'\uf090 Depends To')

                for dTask in depends:
                    action = depends_to_menu.addAction(dTask.name)
                    action.task = dTask

            # Add Dependent Of Menu
            dependent_of = task.dependent_of
            if dependent_of:
                dependent_of_menu = menu.addMenu(u'\uf08b Dependent Of')

                for dTask in dependent_of:
                    action = dependent_of_menu.addAction(dTask.name)
                    action.task = dTask

            if not depends and not dependent_of:
                no_deps_action = menu.addAction(u'\uf00d No Dependencies')
                no_deps_action.setEnabled(False)

        elif isinstance(entity, Project):
            # this is a project!
            project = entity
            menu.addAction(u'\uf115 Create Project Structure')
            if defaults.is_power_user(logged_in_user):
                menu.addSeparator()
                menu.addAction(u'\uf044 Update Project...')
                menu.addSeparator()
                menu.addAction(u'\uf0ae Create Child Task...')

        try:
            # PySide and PySide2
            accepted = QtWidgets.QDialog.DialogCode.Accepted
        except AttributeError:
            # PyQt4
            accepted = QtWidgets.QDialog.Accepted

        selected_item = menu.exec_(global_position)
        if selected_item:
            choice = selected_item.text()[2:]  # text without icon
            from anima import defaults
            url = 'http://%s/%ss/%s/view' % (
                defaults.stalker_server_internal_address,
                entity.entity_type.lower(),
                entity.id
            )
            if choice == 'Open In Web Browser...':
                import webbrowser
                webbrowser.open(url)
            elif choice == 'Copy URL':
                clipboard = QtWidgets.QApplication.clipboard()
                clipboard.setText(url)

                # and warn the user about a new version is created and the
                # clipboard is set to the new version full path
                QtWidgets.QMessageBox.warning(
                    self,
                    "URL Copied To Clipboard",
                    "URL:<br><br>%s<br><br>is copied to clipboard!" %
                    url,
                    QtWidgets.QMessageBox.Ok
                )
            elif choice == 'Copy ID to clipboard':
                clipboard = QtWidgets.QApplication.clipboard()
                clipboard.setText('%s' % entity.id)

                # and warn the user about a new version is created and the
                # clipboard is set to the new version full path
                QtWidgets.QMessageBox.warning(
                    self,
                    "ID Copied To Clipboard",
                    "ID %s is copied to clipboard!" % entity.id,
                    QtWidgets.QMessageBox.Ok
                )

            elif choice == 'Create TimeLog...':
                from anima.ui import time_log_dialog
                time_log_dialog_main_dialog = time_log_dialog.MainDialog(
                    parent=self,
                    task=entity,
                )
                time_log_dialog_main_dialog.exec_()
                result = time_log_dialog_main_dialog.result()
                time_log_dialog_main_dialog.deleteLater()

                if result == accepted:
                    # refresh the task list
                    self.fill()

                    # reselect the same task
                    self.find_and_select_entity_item(entity)

            elif choice == 'Update Task...':
                from anima.ui import task_dialog
                task_main_dialog = task_dialog.MainDialog(
                    parent=self,
                    task=entity
                )
                task_main_dialog.exec_()
                result = task_main_dialog.result()
                task_main_dialog.deleteLater()

                # refresh the task list
                if result == accepted:
                    self.fill()

                    # reselect the same task
                    self.find_and_select_entity_item(entity)

            elif choice == 'Create Child Task...':
                from anima.ui import task_dialog
                task_main_dialog = task_dialog.MainDialog(
                    parent=self,
                    parent_task=entity
                )
                task_main_dialog.exec_()
                result = task_main_dialog.result()
                task = task_main_dialog.task
                task_main_dialog.deleteLater()

                if result == accepted and task:
                    # refresh the task list
                    self.fill()

                    # reselect the same task
                    self.find_and_select_entity_item(task)

            elif choice == 'Duplicate Task Hierarchy...':
                QtWidgets.QMessageBox.warning(
                    self,
                    "Not Implemented!",
                    "Not implemented yet!"
                )
            elif choice == 'Delete Task...':
                QtWidgets.QMessageBox.warning(
                    self,
                    "Not Implemented!",
                    "Not implemented yet!"
                )
            elif choice == 'Create Project Structure':

                answer = QtWidgets.QMessageBox.question(
                    self,
                    'Create Project Structure?',
                    "This will create project folders, OK?",
                    QtWidgets.QMessageBox.Yes,
                    QtWidgets.QMessageBox.No
                )
                if answer == QtWidgets.QMessageBox.Yes:
                    from anima import utils
                    try:
                        utils.create_project_structure(entity)
                    except Exception as e:
                        pass
                    finally:
                        QtWidgets.QMessageBox.information(
                            self,
                            'Project Structure is created!',
                            'Project Structure is created!',
                        )
                else:
                    return

            elif choice == 'Update Project...':
                from anima.ui import project_dialog
                project_main_dialog = project_dialog.MainDialog(
                    parent=self,
                    project=entity
                )
                project_main_dialog.exec_()
                result = project_main_dialog.result()

                # refresh the task list
                if result == accepted:
                    self.fill()

                    # reselect the same task
                    self.find_and_select_entity_item(entity)

                project_main_dialog.deleteLater()

            else:
                # go to the dependencies
                dep_task = selected_item.task
                self.find_and_select_entity_item(
                    dep_task,
                    self
                )

    def find_and_select_entity_item(self, task, tree_view=None):
        """finds and selects the task in the given tree_view item
        """
        if not task:
            return

        if not tree_view:
            tree_view = self

        item = self.load_task_item_hierarchy(task, tree_view)

        selection_model = self.selectionModel()
        if not item:
            selection_model.clearSelection()
            return

        try:
            selection_model.select(
                item.index(),
                QtGui.QItemSelectionModel.ClearAndSelect
            )
        except AttributeError:  # Fix for Qt5
            selection_model.select(
                item.index(),
                QtCore.QItemSelectionModel.ClearAndSelect
            )

        self.setCurrentIndex(item.index())

        self.scrollTo(
            item.index(), QtWidgets.QAbstractItemView.PositionAtBottom
        )
        return item

    def load_task_item_hierarchy(self, task, tree_view):
        """loads the TaskItem related to the given task in the given tree_view

        :return: TaskItem instance
        """
        if not task:
            return

        self.is_updating = True
        item = self.find_entity_item(task)
        if not item:
            # the item is not loaded to the UI yet
            # start loading its parents
            # start from the project
            item = self.find_entity_item(task.project, tree_view)
            logger.debug('item for project: %s' % item)

            if item:
                tree_view.setExpanded(item.index(), True)

            if task.parents:
                # now starting from the most outer parent expand the tasks
                for parent in task.parents:
                    item = self.find_entity_item(parent, tree_view)

                    if item:
                        tree_view.setExpanded(item.index(), True)

            # finally select the task
            item = self.find_entity_item(task, tree_view)

            if not item:
                # still no item
                logger.debug('can not find item')

        self.is_updating = False
        return item

    def find_entity_item(self, entity, tree_view=None):
        """finds the item related to the stalker entity in the given
        QtTreeView
        """
        if not entity:
            return None

        if tree_view is None:
            tree_view = self

        indexes = self.get_item_indices_containing_text(entity.name, tree_view)
        model = tree_view.model()
        logger.debug('items matching name : %s' % indexes)
        for index in indexes:
            item = model.itemFromIndex(index)
            if item:
                if item.task.id == entity.id:
                    return item
        return None

    @classmethod
    def get_item_indices_containing_text(cls, text, tree_view):
        """returns the indexes of the item indices containing the given text
        """
        model = tree_view.model()
        logger.debug('searching for text : %s' % text)
        return model.match(
            model.index(0, 0),
            0,
            text,
            -1,
            QtCore.Qt.MatchRecursive
        )

    def get_task_id(self):
        """returns the task from the UI, it is an task, asset, shot, sequence
        or project
        """
        task_id = None
        selection_model = self.selectionModel()
        logger.debug('selection_model: %s' % selection_model)

        indexes = selection_model.selectedIndexes()
        logger.debug('selected indexes : %s' % indexes)

        if indexes:
            current_index = indexes[0]
            logger.debug('current_index : %s' % current_index)

            item_model = self.model()
            current_item = item_model.itemFromIndex(current_index)

            if current_item:
                task_id = current_item.task.id

        logger.debug('task_id: %s' % task_id)
        return task_id
