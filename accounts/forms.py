from django import forms
from .models import Referral


class ReferralForm(forms.ModelForm):
    class Meta:
        model = Referral
        fields = ['code', 'referrer']

    def clean_code(self):
        code = self.cleaned_data['code']
        qs = Referral.objects.filter(code=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Referral code must be unique.")
        return code
