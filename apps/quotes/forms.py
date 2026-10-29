from django import forms
from django.forms import inlineformset_factory

from apps.clinic.models import PatientProfile, Treatment
from apps.core.forms import DateInput, DentistScopedForm, StyledModelForm

from .models import Quote, QuoteItem


class QuoteForm(DentistScopedForm):
    scoped_fields = {
        "lead": lambda d: d.leads.all(),
        "patient": lambda d: PatientProfile.objects.for_dentist(d).select_related("user"),
        "treatment": lambda d: Treatment.objects.for_dentist(d),
    }

    class Meta:
        model = Quote
        fields = ["patient", "lead", "treatment", "recipient_name", "recipient_email", "recipient_whatsapp", "title", "intro",
                  "payment_terms", "timeline", "valid_until", "attachment"]
        widgets = {"valid_until": DateInput(), "intro": forms.Textarea(attrs={"rows": 4}),
                   "payment_terms": forms.Textarea(attrs={"rows": 3})}

    def clean_attachment(self):
        from apps.core.files import validate_pdf

        f = self.cleaned_data.get("attachment")
        if f and hasattr(f, "content_type"):
            validate_pdf(f)
        return f


class QuoteItemForm(StyledModelForm):
    class Meta:
        model = QuoteItem
        fields = ["description", "region", "quantity", "unit_amount"]


ItemFormSet = inlineformset_factory(Quote, QuoteItem, form=QuoteItemForm, extra=1, can_delete=True, min_num=1, validate_min=True)
