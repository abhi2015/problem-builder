# -*- coding: utf-8 -*-


# Imports ###########################################################

import logging

from xblock.core import XBlock
from xblock.fields import Scope, String
from xblock.fragment import Fragment

from .utils import load_resource, render_template


# Globals ###########################################################

log = logging.getLogger(__name__)


# Functions #########################################################

def commas_to_list(commas_str):
    """
    Converts a comma-separated string to a list
    """
    if commas_str is None:
        return None # Means default value (which can be non-empty)
    elif commas_str == '':
        return [] # Means empty list
    else:
        return commas_str.split(',')


# Classes ###########################################################

class QuizzBlock(XBlock):
    """
    An XBlock used to ask multiple-choice questions

    Must be a child of a MentoringBlock. Allow to display a tip/advice depending on the 
    values entered by the student, and supports multiple types of multiple-choice
    set, with preset choices and author-defined values.
    """
    question = String(help="Question to ask the student", scope=Scope.content, default="")
    type = String(help="Type of quizz", scope=Scope.content, default="yes-no-unsure")
    student_choice = String(help="Last input submitted by the student", default="", scope=Scope.user_state)
    low = String(help="Label for low ratings", scope=Scope.content, default="Less")
    high = String(help="Label for high ratings", scope=Scope.content, default="More")
    has_children = True

    @classmethod
    def parse_xml(cls, node, runtime, keys):
        block = runtime.construct_xblock_from_class(cls, keys)

        for child in node:
            if child.tag == "question":
                block.question = child.text
            else:
                block.runtime.add_node_as_child(block, child)

        for name, value in node.items():
            if name in block.fields:
                setattr(block, name, value)

        return block

    def student_view(self, context=None):  # pylint: disable=W0613
        """Returns default student view."""
        return Fragment(u"<p>I can only appear inside mentoring blocks.</p>")

    def mentoring_view(self, context=None):
        if self.type not in ('yes-no-unsure', 'rating-unsure'):
            raise ValueError, u'Invalid value for QuizzBlock.type: `{}`'.format(self.type)

        template_path = 'templates/html/quizz_{}.html'.format(self.type)
        html = render_template(template_path, {
            'self': self,
        })

        fragment = Fragment(html)
        fragment.add_css(load_resource('static/css/quizz.css'))
        fragment.add_javascript(load_resource('static/js/quizz.js'))
        fragment.initialize_js('QuizzBlock')
        return fragment

    def submit(self, submission):
        log.debug(u'Received quizz submission: "%s"', submission)

        completed = True
        formatted_tips_list = []
        for tip in self.get_tips():
            completed = completed and tip.is_completed(submission)
            if tip.is_tip_displayed(submission):
                formatted_tips_list.append(tip.render(submission))

        if formatted_tips_list:
            formatted_tips = render_template('templates/html/tip_group.html', {
                'self': self,
                'tips': formatted_tips_list,
                'submission': submission,
            })
        else:
            formatted_tips = u''

        self.student_choice = submission
        result = {
            'submission': submission,
            'completed': completed,
            'tips': formatted_tips,
        }
        log.debug(u'Quizz submission result: %s', result)
        return result

    def get_tips(self):
        """
        Returns the tips contained in this block
        """
        tips = []
        for child_id in self.children:  # pylint: disable=E1101
            child = self.runtime.get_block(child_id)
            if child.xml_element_name() == 'tip':
                tips.append(child)
        return tips


class QuizzTipBlock(XBlock):
    """
    Each quizz
    """
    content = String(help="Text of the tip to provide if needed", scope=Scope.content, default="")
    display = String(help="List of choices to display the tip for", scope=Scope.content, default=None)
    reject = String(help="List of choices to reject", scope=Scope.content, default=None)
    
    def render(self, submission):
        """
        Returns a string containing the formatted tip
        """
        return render_template('templates/html/tip.html', {
            'self': self,
        })

    def is_completed(self, submission):
        return submission and submission not in self.reject_with_defaults

    def is_tip_displayed(self, submission):
        return not submission or submission in self.display_with_defaults

    @property
    def reject_with_defaults(self):
        reject = commas_to_list(self.reject)
        log.debug(reject)
        if reject is None:
            quizz = self.runtime.get_block(self.parent)
            if quizz.type == 'yes-no-unsure':
                return ['no', 'unsure']
            elif quizz.type == 'rating-unsure':
                return ['1', '2', '3', 'unsure']
        else:
            return reject

    @property
    def display_with_defaults(self):
        display = commas_to_list(self.display)
        if display is None:
            display = self.reject_with_defaults
        else:
            display += [choice for choice in self.reject_with_defaults
                               if choice not in display]
        return display
