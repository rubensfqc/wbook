from django import forms


class StyledFormMixin:
    """Adds the CSS component classes to every widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, (forms.CheckboxInput,)):
                css = "checkbox"
            elif isinstance(w, (forms.CheckboxSelectMultiple, forms.RadioSelect)):
                css = ""
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                css = "select"
            elif isinstance(w, forms.FileInput):
                css = "file-input"
            else:
                css = "input"
            if css:
                w.attrs["class"] = (w.attrs.get("class", "") + " " + css).strip()


class StyledForm(StyledFormMixin, forms.Form):
    pass


class StyledModelForm(StyledFormMixin, forms.ModelForm):
    pass


class DentistScopedForm(StyledModelForm):
    """FK querysets restricted to self.dentist (applied on GET and POST)."""

    scoped_fields = {}  # field name -> callable(dentist) -> queryset

    def __init__(self, *args, dentist=None, **kwargs):
        self.dentist = dentist
        super().__init__(*args, **kwargs)
        for name, qs in self.scoped_fields.items():
            if name in self.fields:
                self.fields[name].queryset = qs(dentist)


class LenientURLField(forms.URLField):
    """URL typed without a scheme ("www.clinica.com.br") is accepted and saved as https://….

    Uses a text input (inputmode=url) because the browser's own type="url" check rejects
    anything without "https://" before the form is even sent.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("assume_scheme", "https")
        kwargs.setdefault("widget", forms.TextInput(attrs={"inputmode": "url", "autocapitalize": "off", "spellcheck": "false"}))
        super().__init__(**kwargs)

    def to_python(self, value):
        value = (value or "").strip()
        if value and "://" not in value:
            value = "https://" + value.lstrip("/")
        return super().to_python(value)


class InstagramURLField(LenientURLField):
    """Accepts a full link, "instagram.com/perfil", "@perfil" or just "perfil"."""

    def to_python(self, value):
        value = (value or "").strip()
        if value and "://" not in value and "instagram.com" not in value.lower() and "/" not in value:
            value = "https://www.instagram.com/{}/".format(value.lstrip("@"))
        return super().to_python(value)


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        kwargs.setdefault("format", "%Y-%m-%d")
        super().__init__(**kwargs)


class TimeInput(forms.TimeInput):
    input_type = "time"

    def __init__(self, **kwargs):
        kwargs.setdefault("format", "%H:%M")
        super().__init__(**kwargs)


class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, **kwargs):
        kwargs.setdefault("format", "%Y-%m-%dT%H:%M")
        super().__init__(**kwargs)
