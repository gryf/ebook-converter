from ebook_converter import constants_old


def force_unicode(obj, enc=constants_old.preferred_encoding):
    if isinstance(obj, bytes):
        try:
            obj = obj.decode(enc)
        except Exception:
            try:
                obj = obj.decode(constants_old.filesystem_encoding
                                 if enc == constants_old.preferred_encoding
                                 else constants_old.preferred_encoding)
            except Exception:
                try:
                    obj = obj.decode('utf-8')
                except Exception:
                    obj = repr(obj)
                    if isinstance(obj, bytes):
                        obj = obj.decode('utf-8')
    return obj
