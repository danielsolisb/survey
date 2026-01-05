from django import forms
from .models import Well

class WellForm(forms.ModelForm):
    class Meta:
        model = Well
        fields = ['name', 'location', 'latitude', 'longitude', 'elevation']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all outline-none',
                'placeholder': 'Ej. Sacha-123'
            }),
            'location': forms.TextInput(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all outline-none',
                'placeholder': 'Ej. Campo Sacha, Bloque 60'
            }),
            'latitude': forms.NumberInput(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all outline-none',
                'step': 'any'
            }),
            'longitude': forms.NumberInput(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all outline-none',
                'step': 'any'
            }),
            'elevation': forms.NumberInput(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2.5 text-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all outline-none',
                'step': 'any'
            }),
        }
