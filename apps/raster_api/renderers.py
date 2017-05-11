from rest_framework.renderers import BaseRenderer


class BinaryRenderer(BaseRenderer):
    media_type = '*/*'
    charset = None
    render_style = 'binary'

    def render(self, data, media_type=None, renderer_context=None):
        return data
