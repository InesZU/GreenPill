from flask_wtf import FlaskForm
from wtforms import (
    SelectField,
    StringField, 
    PasswordField, 
    SubmitField, 
    DateField, 
    BooleanField,
    IntegerField,
    TextAreaField
)
from wtforms.validators import (
    DataRequired, 
    Email, 
    Length, 
    EqualTo, 
    NumberRange,
    Optional
)


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=80)
    ])
    email = StringField('Email', validators=[
        DataRequired(),
        Email()
    ])
    age = IntegerField('Age', validators=[
        NumberRange(min=0, max=120, message='Please enter a valid age')
    ])
    gender = SelectField('Gender', choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say')
    ], validators=[DataRequired()])
    allergies = TextAreaField('Allergies (one per line)', validators=[
        Optional()
    ])
    medical_conditions = TextAreaField('Medical Conditions (one per line)', validators=[
        Optional()
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')


class ProfileUpdateForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=80)
    ])
    email = StringField('Email', validators=[
        DataRequired(),
        Email()
    ])
    age = IntegerField('Age', validators=[
        NumberRange(min=0, max=120, message='Please enter a valid age')
    ])
    gender = SelectField('Gender', choices=[    
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say')
    ], validators=[DataRequired()])
    allergies = TextAreaField('Allergies (one per line)', validators=[
        Optional()
    ])
    medical_conditions = TextAreaField('Medical Conditions (one per line)', validators=[
        Optional()
    ])
    submit = SubmitField('Update Profile')
