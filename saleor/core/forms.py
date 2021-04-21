from django import forms

class ResetPassword(forms.Form):
    new_password = forms.CharField(label='new_password',widget=forms.PasswordInput())
    confirm_new_password = forms.CharField(label='Password (again)', widget=forms.PasswordInput())
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