from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, EmailField, SelectField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange, Optional

class LoginForm(FlaskForm):
    email = EmailField('Email', validators=[
        DataRequired(),
        Email()
    ])
    password = PasswordField('Password', validators=[
        DataRequired()
    ])
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=80)
    ])
    email = EmailField('Email', validators=[
        DataRequired(),
        Email()
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6)
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    
    age = IntegerField('Age', validators=[
        DataRequired(),
        NumberRange(min=0, max=120)
    ])
    gender = SelectField('Gender', choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say')
    ], validators=[DataRequired()])
    allergies = TextAreaField('Allergies (one per line)', validators=[Optional()])
    medical_conditions = TextAreaField('Medical Conditions (one per line)', validators=[Optional()])
    
    submit = SubmitField('Register') 