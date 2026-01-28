# Common Issues

Note that if you are using MacOS you may stumble across `URLError` while trying to submit the form.

```shell script
URLError at /contact-us/
<urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] Certificate Verify Failed: Unable to Get Local Issuer Certificate (_ssl.c:1122)>
```

As regards to "[Scraping: SSL: CERTIFICATE_VERIFY_FAILED](https://stackoverflow.com/questions/50236117/scraping-ssl-certificate-verify-failed-error-for-http-en-wikipedia-org)" issue on [Stack Overflow](https://stackoverflow.com), all you need to do is go to *Macintosh HD* → *Applications* → *Python* folder and double click on **Install Certificates.command** file.

![URL Error](contact_form/README/URL%20Error.png)

