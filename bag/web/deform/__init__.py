#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''This package:

* constitutes a third layer of templates on top of the package
  *deform_boostrap*, which skins Deform with Twitter's "bootstrap" library.
* will contain special widgets for Deform.

Our alterations to Deform templates are in the "templates" subdirectory.

Our preferred way of enabling the whole stack is this:

.. code-block:: python

    starter.enable_deform((
        'bag:web/deform/templates',
        'deform_bootstrap:templates',
        'deform:templates',
    ))  # This way you do not config.include('deform_bootstrap')

Here are the changes we've made:

* form.pt: Demands you stick a *csrf_token* onto the form object in order to
  protect against cross-site request forgery. Otherwise, it is identical to
  the template in deform_bootstrap.
* mapping_item.pt: Allows you to pass a *css_class* to any mapping schema, and
  the class appears on the outer item.
* password.pt: Supports *maxlength* and *placeholder* and
  automatically sets *required*.
* textarea.pt: Supports *maxlength* and *placeholder* and
  automatically sets *required*.
* textinput.pt: Supports *maxlength* and *placeholder* and
  automatically sets *required*.
* checkbox.pt: Allows you to pass a *text* argument to a Boolean schema, and
  the text appears on the right of the checkbox.

This has been tested against deform_bootstrap 0.1a5.
'''

from __future__ import absolute_import
from __future__ import unicode_literals  # unicode by default
import colander as c
import deform.widget as w
from ...sqlalchemy.tricks import length


def lengthen(max, min=0, size=None, widget_cls=w.TextInputWidget,
             typ='input', placeholder=None, validators=None):
    '''Use this to easily create well-sized inputs.

    Returns a dict containing *widget* and *validator*,
    all concerned about length.

    If the parameter *max* is not an integer, it is treated as a model property
    from which the real *max* can be inferred.
    '''
    if not isinstance(max, int):
        max = length(max)
    if not size:
        size = max if max <= 35 else 35 + (max - 35) / 4
    if size > 60:
        size = 60
    validator = c.Length(min=min, max=max)
    if validators:
        validator = c.All(validator, *validators)
    return dict(widget=widget_cls(size=size, maxlength=max,
        placeholder=placeholder, typ=typ), validator=validator)


"""
import deform as d


class SlugWidget(d.widget.TextInputWidget):
    '''Lets you pass a *prefix* which will appear just before the <input>.
    TODO: This feature is probably no longer necessary
    since deform_bootstrap has *input_prepend* and *input_append*.
    '''
    # TODO: Make the slug input reflect the content of another input
    template = 'slug'
"""
