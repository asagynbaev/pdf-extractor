# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in PDF Extractor, please email security researchers to report it responsibly rather than posting it publicly.

Steps to report:
1. Do not open a public issue
2. Contact the maintainers with details of the vulnerability
3. Include proof of concept if available
4. Allow time for the maintainers to address the issue

## Security Considerations

### When Extracting PDFs

- **Malicious PDFs**: Be cautious when processing PDFs from untrusted sources
- **OCR Timeouts**: The tool includes a 60-second OCR timeout by default to prevent denial-of-service attacks from corrupted images
- **File Permissions**: Ensure the output directory is in a secure location with appropriate file permissions
- **Sensitive Data**: Be aware that extracted text may contain sensitive information - handle output files appropriately

### Dependencies

This project uses the following key dependencies:
- **PyMuPDF (fitz)** - for PDF reading and processing
- **PaddleOCR** - for optical character recognition
- **Pillow** - for image processing
- **NumPy** - for numerical operations

All dependencies are pinned to specific versions in `requirements.txt` for reproducibility and security.

## Best Practices

1. **Keep dependencies updated**: Periodically run `pip install --upgrade -r requirements.txt` to get security patches
2. **Validate input**: Ensure PDF files come from trusted sources
3. **Monitor output**: Review extraction logs for errors or warnings
4. **Secure storage**: Store extracted datasets in secure locations with appropriate access controls
5. **Use timeouts**: The default OCR timeout of 60 seconds is recommended; adjust only if needed
6. **Test batches**: Start with small batches of PDFs before processing large collections

## Supported Versions

Only the latest version of PDF Extractor receives security updates. We recommend always running the latest version.

## Security Incident Response

In case of a security incident:
1. A security patch will be released as soon as possible
2. An advisory will be published with details and mitigation steps
3. Users will be notified through GitHub Security Advisories

## Additional Resources

- [Python Security](https://www.python.org/dev/security/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Secure Coding Guidelines](https://www.securecoding.cert.org/confluence/display/java/SEI+CERT+Java+Coding+Standards)
