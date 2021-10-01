# Contact Form

## Description

A very basic contact form with CAPTCHA module that protects you against spam based on two articles from LearnWagtail website (["Contact Forms"](https://learnwagtail.com/tutorials/contact-forms) and ["Adding Recaptcha to Your Contact Forms"](https://learnwagtail.com/tutorials/adding-recaptcha-to-your-contact-forms)).

### Installing

Installation process is exactly the same as for regular [Django application](https://docs.djangoproject.com/en/3.2/intro/tutorial01/).

### Dependencies

- django-widget-tweaks (https://github.com/jazzband/django-widget-tweaks)
- wagtail-django-recaptcha (https://github.com/springload/wagtail-django-recaptcha)
```python
INSTALLED_APPS = [
    'captcha',
    'wagtailcaptcha'
]
```

- `wagtail.contrib.forms`
```python
INSTALLED_APPS = [
    'wagtail.contrib.forms'
]
```

### Common Issues

Note that if you are using MacOS you may stumble across `URLError` while trying to submit the form.

```shell script
URLError at /contact-us/
<urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] Certificate Verify Failed: Unable to Get Local Issuer Certificate (_ssl.c:1122)>
```

As regards to "[Scraping: SSL: CERTIFICATE_VERIFY_FAILED](https://stackoverflow.com/questions/50236117/scraping-ssl-certificate-verify-failed-error-for-http-en-wikipedia-org)" issue on [Stack Overflow](https://stackoverflow.com), all you need to do is go to *Macintosh HD* → *Applications* → *Python* folder and double click on **Install Certificates.command** file.

![URL Error](./readme/URL%20Error.png)

## Screenshots

#### Contact Form

![Contact Us](./readme/Contact%20Us.png)

#### "Thank You" Page

!["Thank You" Page](./readme/Thank%20You%20Page.png)

## Form Fields 

- Full Name
- E-Mail Address
- Message
- CAPTCHA

## Custom Form Fields 
- *Intro* Text
- *Thank You* Text
- E-Mail ("From" Address)
- E-Mail ("To" Address)
- E-Mail Subject

## Authors

[Filip Woźniak](https://github.com/FilipWozniak)