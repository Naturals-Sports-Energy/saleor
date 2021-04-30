from django import forms

class ResetPassword(forms.Form):
    error_css_class='error'
    required_css_class='required'
    new_password = forms.CharField(widget=forms.PasswordInput(attrs={'class':'form-control','id':'new_password','placeholder':'password'}))
    confirm_new_password = forms.CharField(widget=forms.PasswordInput(attrs={'class':'form-control', 'id':'confirm_new_password','placeholder':'password'}))
    email = forms.CharField(widget=forms.HiddenInput,required=False)
    token = forms.CharField(widget=forms.HiddenInput,required=False)
    def clean(self):
        cleaned_data = super().clean()
        valpwd = cleaned_data['new_password']
        valrpwd = cleaned_data['confirm_new_password']
        print("valpwd: {}".format(valpwd))
        print("valrpwd: {}".format(valrpwd))
        if valpwd!=valrpwd:
            print("raising error")
            raise forms.ValidationError('Password Not Matched')