# Common Issues

If you are using `MacOS` you may encounter `URLError` while trying to submit the form.

```shell
URLError at /contact-us/
[SSL: CERTIFICATE_VERIFY_FAILED] Certificate Verify Failed
```

![3.png](../README/images/3.png)

So, to resolve this issue, please navigate to `Macintosh HD` > `Applications` > `Python` and double-click on
`Install Certificates.command`, as described in
this [thread](https://stackoverflow.com/questions/50236117/scraping-ssl-certificate-verify-failed-error-for-http-en-wikipedia-org).
