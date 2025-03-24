from django import forms
from xliff_manager.models import Languages

class LanguageSelectionForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(LanguageSelectionForm, self).__init__(*args, **kwargs)
        #self.fields['languages'].widget.attrs = {'class': 'form-select'}
        self.fields['languages'].choices = [(lang.id, lang.name) for lang in Languages.objects.all()]

    languages = forms.ChoiceField(
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Select the language to manage",
        required=True
    )