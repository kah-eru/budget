from django import template

register = template.Library()


@register.filter
def dollars(cents):
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents) // 100:,}.{abs(cents) % 100:02d}"


@register.filter
def signed(cents):
    """+$1.00 for money in, −$1.00 (a true minus) for money out, $0.00 for nothing."""
    return ("+" if cents > 0 else "−" if cents < 0 else "") + dollars(abs(cents))
