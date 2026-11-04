"""Minha página URL fields and the 'Tipos de consulta' formset on /app/configuracoes/agenda/."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.agenda.models import Appointment
from apps.landing.forms import LandingPageForm

from .helpers import make_dentist, make_patient


class LandingUrlTests(TestCase):
    def setUp(self):
        self.d = make_dentist()

    def _clean(self, **data):
        base = {"accent": "teal", "is_published": "on"}
        f = LandingPageForm({**base, **data}, instance=self.d.landing)
        self.assertTrue(f.is_valid(), f.errors)
        return f.cleaned_data

    def test_website_without_scheme_gets_https(self):
        self.assertEqual(self._clean(website="www.clinica.com.br")["website"], "https://www.clinica.com.br")
        self.assertEqual(self._clean(website="clinica.com.br/contato")["website"], "https://clinica.com.br/contato")
        self.assertEqual(self._clean(website="http://clinica.com.br")["website"], "http://clinica.com.br")

    def test_instagram_accepts_handle_or_link(self):
        self.assertEqual(self._clean(instagram="@dra.ana")["instagram"], "https://www.instagram.com/dra.ana/")
        self.assertEqual(self._clean(instagram="dra_ana")["instagram"], "https://www.instagram.com/dra_ana/")
        self.assertEqual(self._clean(instagram="instagram.com/dra.ana")["instagram"], "https://instagram.com/dra.ana")
        self.assertEqual(self._clean(instagram="https://www.instagram.com/x/")["instagram"], "https://www.instagram.com/x/")
        self.assertEqual(self._clean(instagram="")["instagram"], "")

    def test_inputs_are_not_browser_url_type(self):
        html = str(LandingPageForm(instance=self.d.landing)["website"])
        self.assertNotIn('type="url"', html)

    def test_editor_saves_short_url(self):
        self.client.force_login(self.d.user)
        r = self.client.post("/app/leads/minha-pagina/", {"accent": "teal", "website": "www.clinica.com.br",
                                                          "instagram": "@dra.ana"})
        self.assertEqual(r.status_code, 302)
        self.d.landing.refresh_from_db()
        self.assertEqual(self.d.landing.website, "https://www.clinica.com.br")
        self.assertEqual(self.d.landing.instagram, "https://www.instagram.com/dra.ana/")


class TypeFormsetTests(TestCase):
    URL = "/app/configuracoes/agenda/"

    def setUp(self):
        self.d = make_dentist()
        self.client.force_login(self.d.user)
        self.types = list(self.d.appointment_types.all())

    def _data(self, rows, initial=None):
        r = self.client.get(self.URL)
        ctx = r.context
        data = {}
        for prefix, form in (("s", ctx["sform"]),):
            for name, field in form.fields.items():
                v = form.initial.get(name, field.initial)
                if isinstance(v, bool):
                    if v:
                        data[f"{prefix}-{name}"] = "on"
                elif v is not None:
                    data[f"{prefix}-{name}"] = v
        hours = ctx["hours"]
        data.update({"h-TOTAL_FORMS": hours.initial_form_count(), "h-INITIAL_FORMS": hours.initial_form_count(),
                     "h-MIN_NUM_FORMS": 0, "h-MAX_NUM_FORMS": 1000})
        for i, f in enumerate(hours.forms[:hours.initial_form_count()]):
            data.update({f"h-{i}-id": f.instance.pk, f"h-{i}-weekday": f.instance.weekday,
                         f"h-{i}-start": f.instance.start.strftime("%H:%M"), f"h-{i}-end": f.instance.end.strftime("%H:%M")})
        data.update({"t-TOTAL_FORMS": len(rows), "t-INITIAL_FORMS": initial if initial is not None else len(self.types),
                     "t-MIN_NUM_FORMS": 1, "t-MAX_NUM_FORMS": 1000})
        for i, row in enumerate(rows):
            for k, v in row.items():
                if v is not None:
                    data[f"t-{i}-{k}"] = v
        return data

    def _row(self, t=None, **kw):
        row = {"id": t.pk if t else "", "name": t.name if t else "", "duration_min": t.duration_min if t else 30,
               "buffer_min": 0, "price": "", "colour": "#0f766e", "is_active": "on", "order": 0}
        row.update(kw)
        return row

    def test_no_blank_extra_row(self):
        r = self.client.get(self.URL)
        self.assertEqual(len(r.context["types"].forms), len(self.types))
        self.assertContains(r, "data-formset-add")

    def test_add_and_remove(self):
        rows = [self._row(t) for t in self.types]
        rows[-1]["DELETE"] = "on"
        rows.append(self._row(name="Clareamento", duration_min=60))
        r = self.client.post(self.URL, self._data(rows))
        self.assertEqual(r.status_code, 302)
        names = set(self.d.appointment_types.values_list("name", flat=True))
        self.assertIn("Clareamento", names)
        self.assertNotIn(self.types[-1].name, names)

    def test_removed_blank_new_row_is_ignored(self):
        rows = [self._row(t) for t in self.types] + [self._row(name="", duration_min="", DELETE="on")]
        self.assertEqual(self.client.post(self.URL, self._data(rows)).status_code, 302)

    def test_cannot_remove_all(self):
        rows = [self._row(t, DELETE="on") for t in self.types]
        r = self.client.post(self.URL, self._data(rows))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Cadastre pelo menos um tipo de consulta.")
        self.assertEqual(self.d.appointment_types.count(), len(self.types))

    def test_needs_one_active(self):
        rows = [self._row(t, is_active=None) for t in self.types]
        r = self.client.post(self.URL, self._data(rows))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Mantenha pelo menos um tipo de consulta ativo.")

    def test_field_errors_are_shown(self):
        rows = [self._row(t) for t in self.types]
        rows[0]["duration_min"] = ""
        r = self.client.post(self.URL, self._data(rows))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "field-error")

    def test_type_in_use_is_not_deleted_and_nothing_half_saved(self):
        p = make_patient(self.d)
        t = self.types[0]
        start = timezone.now() + timedelta(days=3)
        Appointment.objects.create(dentist=self.d, patient=p, type=t, start=start, end=start + timedelta(minutes=30),
                                   status=Appointment.Status.CONFIRMED)
        rows = [self._row(x) for x in self.types]
        rows[0]["DELETE"] = "on"
        rows[1]["name"] = "Renomeado"
        r = self.client.post(self.URL, self._data(rows))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(self.d.appointment_types.filter(pk=t.pk).exists())
        self.assertFalse(self.d.appointment_types.filter(name="Renomeado").exists())


class PublicPageLinksTests(TestCase):
    def test_links_only_when_filled(self):
        d = make_dentist()
        r = self.client.get(f"/{d.slug}/")
        self.assertNotContains(r, "instagram.com")
        d.landing.instagram = "https://www.instagram.com/dra.ana/"
        d.landing.website = "https://www.clinica.com.br"
        d.landing.save()
        r = self.client.get(f"/{d.slug}/")
        self.assertContains(r, 'href="https://www.instagram.com/dra.ana/"')
        self.assertContains(r, 'href="https://www.clinica.com.br"')
