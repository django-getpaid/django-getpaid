#
# This work by Patryk Zawadzki is licensed under a Creative Commons
# Attribution-NonCommercial-ShareAlike 2.5 Poland.
#
# taken from:
# http://room-303.com/blog/2010/04/27/django-abstrakcji-ciag-dalszy/
# http://gist.github.com/584106
#


class AbstractMixin(object):
    _classcache = {}

    @classmethod
    def contribute(cls):
        return {}

    @classmethod
    def construct(cls, *args, **kwargs):
        attrs = cls.contribute(*args, **kwargs)
        attrs.update({
            '__module__': cls.__module__,
            'Meta': type('Meta', (), {'abstract': True}),
        })
        key = (args, tuple(kwargs.items()))
        if key not in cls._classcache:
            clsname = ('%s%x' % (cls.__name__, hash(key))) \
                .replace('-', '_')
            cls._classcache[key] = type(clsname, (cls, ), attrs)
        return cls._classcache[key]
