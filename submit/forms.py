from django import forms
from django.forms import formset_factory

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean

        def clean_single_file(file):
            if file and hasattr(file, 'size') and file.size == 0:
                return file
            else:
                return single_file_clean(file, initial)

        if isinstance(data, (list, tuple)):
            result = [clean_single_file(f) for f in data]
        else:
            result = [clean_single_file(data)]
        return result


class FileInputForm(forms.Form):
    choice_field = forms.ChoiceField(choices=[("TopTrjPair", "Topology and trajectory files"), ("MaestroDir", "Maestro Directory")])
    file_field = MultipleFileField()
    paths_field = forms.JSONField(required=False)
    value_field = forms.FloatField()
    template_name = "submit/form_snippet.html"

class InputDetails(forms.Form):
    email_field = forms.EmailField(required=False)
    use_common_numbering = forms.BooleanField(required=False)
    name_VOI = forms.CharField(required=False)


FileInputFormSet = formset_factory(FileInputForm)

