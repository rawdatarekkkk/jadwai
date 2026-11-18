"""Verified scheduling explanations for common follow-up discussions."""
import re


def explain(raw, view):
    text = raw.lower()
    ar = bool(re.search(r'[؀-ۿ]', text))
    discussion = bool(re.search(r'explain|why|could|would|what if|before changing|do not change|اشرح|ليه|وضح|ممكن', text))
    if not discussion:
        return None
    if re.search(r'shared.*(?:fixed|lock)|(?:fixed|lock).*shared|المشتركة.*تثبيت|ثبت.*المشتركة', text):
        return ('نعم، يمكن اقتراح تثبيت المحاضرات المشتركة ثم إعادة جدولة بقية حصص المجموعة حولها. هذا يقلل الخيارات المتاحة، لذلك يجب أن يتحقق المحلل من إمكانية تحقيق أيام الإجازة مع كل القيود. أي مجموعة أو مسودة تريد استخدامها؟' if ar else
                'Yes. We can propose locks for the shared lectures, then reschedule the group’s other sessions around them. That leaves fewer choices, so the solver must check whether the requested free days fit while respecting every constraint. Which group or draft should we use?')
    if re.search(r'free days?|days? off|ايام.*اجازة|يومين.*(?:اجازة|إجازة)', text):
        count = len(view['calendar']['days'])
        two = bool(re.search(r'two|\b2\b|يومين', text))
        opening = (f'Two free days would leave {count - 2} teaching days in this calendar. ' if two else 'Free days mean fitting the same required sessions into fewer teaching days. ')
        return ('أيام الإجازة تعني وضع نفس الحصص الأسبوعية المطلوبة في أيام تدريس أقل، دون إلغاء حصص. قد يزيد الحمل اليومي وتقل الأوقات المتاحة. أي محاضرة مشتركة يجب أن تناسب كل المجموعات التي تحضرها، وكذلك المحاضر والقاعة. أي مجموعة تريد تقييمها؟' if ar else
                opening + 'The required sessions stay the same; none are cancelled. Daily load may increase and available slots may shrink. A shared lecture can move only when every attending group, its instructor and a suitable room are free. Which group should I assess?')
    return None
