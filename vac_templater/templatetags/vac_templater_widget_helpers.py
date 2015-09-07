# -*- coding: utf-8 -*-

'''
:copyright: (c) 2015 by Allenta Consulting S.L. <info@allenta.com>.
:license: GPL, see LICENSE.txt for more details.
'''

from __future__ import absolute_import
import re
from django.template import Library, Node, TemplateSyntaxError
register = Library()

##
## Based on http://pypi.python.org/pypi/django-widget-tweaks.
##


def silence_without_field(fn):
    def wrapped(field, attr):
        if not field:
            return ''
        else:
            return fn(field, attr)
    return wrapped


def _process_field_attributes(field, attr, process):
    # Split attribute name and value from 'attr:value' string.
    params = attr.split(':', 1)
    attribute = params[0]
    value = params[1] if len(params) == 2 else ''

    # Decorate field.as_widget method with updated attributes.
    old_as_widget = field.as_widget

    def as_widget(self, widget=None, attrs=None, only_initial=False):
        attrs = attrs or {}
        process(widget or self.field.widget, attrs, attribute, value)
        return old_as_widget(widget, attrs, only_initial)

    bound_method = type(old_as_widget)
    try:
        field.as_widget = bound_method(as_widget, field, field.__class__)
    except TypeError:  # Python 3.
        field.as_widget = bound_method(as_widget, field)
    return field


@register.filter('attr')
@silence_without_field
def set_attr(field, attr):
    def process(widget, attrs, attribute, value):
        attrs[attribute] = value
    return _process_field_attributes(field, attr, process)


@register.filter('append_attr')
@silence_without_field
def append_attr(field, attr):
    def process(widget, attrs, attribute, value):
        if attrs.get(attribute):
            attrs[attribute] += ' ' + value
        elif widget.attrs.get(attribute):
            attrs[attribute] = widget.attrs[attribute] + ' ' + value
        else:
            attrs[attribute] = value
    return _process_field_attributes(field, attr, process)


@register.filter('add_class')
@silence_without_field
def add_class(field, css_class):
    return append_attr(field, 'class:' + css_class)


@register.filter('add_error_class')
@silence_without_field
def add_error_class(field, css_class):
    if hasattr(field, 'errors') and field.errors:
        return add_class(field, css_class)
    return field


@register.filter('set_data')
@silence_without_field
def set_data(field, data):
    return set_attr(field, 'data-' + data)

# render_field tag

ATTRIBUTE_RE = re.compile(r'''
    (?P<attr>
        [\w_-]+
    )
    (?P<sign>
        \+?=
    )
    (?P<value>
    ['"]? # start quote
        [^"']*
    ['"]? # end quote
    )
''', re.VERBOSE | re.UNICODE)


@register.tag
def render_field(parser, token):
    '''Render a form field using given attribute-value pairs.

    Takes form field as first argument and list of attribute-value pairs for
    all other arguments.  Attribute-value pairs should be in the form of
    attribute=value or attribute="a value" for assignment and attribute+=value
    or attribute+="value" for appending.

    '''
    error_msg = (
        '%r tag requires a form field followed by a list of attributes and '
        'values in the form attr="value"' % token.split_contents()[0])
    try:
        bits = token.split_contents()
        tag_name = bits[0]
        form_field = bits[1]
        attr_list = bits[2:]
    except ValueError:
        raise TemplateSyntaxError(error_msg)

    form_field = parser.compile_filter(form_field)

    set_attrs = []
    append_attrs = []
    for pair in attr_list:
        match = ATTRIBUTE_RE.match(pair)
        if not match:
            raise TemplateSyntaxError(error_msg + ': %s' % pair)
        dct = match.groupdict()
        attr, sign, value = \
            dct['attr'], dct['sign'], parser.compile_filter(dct['value'])
        if sign == '=':
            set_attrs.append((attr, value))
        else:
            append_attrs.append((attr, value))

    return FieldAttributeNode(form_field, set_attrs, append_attrs)


class FieldAttributeNode(Node):
    def __init__(self, field, set_attrs, append_attrs):
        self.field = field
        self.set_attrs = set_attrs
        self.append_attrs = append_attrs

    def render(self, context):
        bounded_field = self.field.resolve(context)
        for k, v in self.set_attrs:
            bounded_field = set_attr(
                bounded_field, '%s:%s' % (k, v.resolve(context)))
        for k, v in self.append_attrs:
            bounded_field = append_attr(
                bounded_field, '%s:%s' % (k, v.resolve(context)))
        return bounded_field


@register.filter(name='field_type')
def field_type(field):
    '''Template filter that returns field class name (in lower case).

    E.g. if field is CharField then {{ field|field_type }} will
    return 'charfield'.
    '''
    if hasattr(field, 'field') and field.field:
        return field.field.__class__.__name__.lower()
    return ''


@register.filter(name='widget_type')
def widget_type(field):
    '''Template filter that returns field widget class name (in lower case).

    E.g. if field's widget is TextInput then {{ field|widget_type }} will
    return 'textinput'.
    '''
    if hasattr(field, 'field') and \
       hasattr(field.field, 'widget') and \
       field.field.widget:
        return field.field.widget.__class__.__name__.lower()
    return ''