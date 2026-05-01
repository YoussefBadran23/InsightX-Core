/**
 * Lightweight i18n module — no external dependency required.
 * Supports English (en) and Arabic (ar).
 * Usage: const { t } = useTranslation();
 */

export type Locale = 'en' | 'ar';

const translations = {
  en: {
    // Header
    login:           'Login',
    language: 'Language',
    toggleTheme: 'Toggle Theme',
    login: 'Login',
    signup: 'Sign Up',
    startFree: 'Start Analysis Free',
    viewDashboard: 'View Dashboard',
    tagline: 'Unlock the Power of',
    tagline2: 'AI Business Analytics',
    description: 'Transform your sales data into actionable insights instantly. Upload your CSV, let our AI engine analyze trends, and get accurate forecasts to grow your business.',
    noCard: 'No credit card required',
    freeTrial: '14-day free trial',
    featureStart: 'Easy to Start',
    featureStartDesc: 'Upload your CSV file and our AI engine instantly maps your data structure.',
    featureAnalytics: 'Deep Analytics',
    featureAnalyticsDesc: 'Get comprehensive dashboards showing key performance metrics and trends.',
    featureForecasting: 'Smart Forecasting',
    featureForecastingDesc: 'Predict future sales and inventory needs with machine learning models.',
    featureSegmentation: 'Customer Insights',
    featureSegmentationDesc: 'Automatically segment your customers based on purchasing behavior.',
    support: 'Support',
    terms: 'Terms',
    privacy: 'Privacy',
    footer: '© 2026 InsightX Inc. All rights reserved.',
    
    // Login
    signInTitle: 'Sign In to InsightX',
    signInDesc: 'Secure access to your dashboard',
    emailAddress: 'Email Address',
    password: 'Password',
    forgotPassword: 'Forgot password?',
    logInBtn: 'Log In',
    loggingInBtn: 'Logging In...',
    noAccount: "Don't have an account?",

    // Signup
    createAccountTitle: 'Create Your InsightX Account',
    createAccountDesc: 'Join thousands of companies using InsightX for data analytics.',
    fullName: 'Full Name / Company',
    workEmail: 'Work Email',
    confirmPassword: 'Confirm Password',
    signUpBtn: 'Sign Up',
    signingUpBtn: 'Creating Account...',
    haveAccount: 'Already have an account?',
    helpCenter: 'Help Center',

    // Support
    helpCenterTitle: 'Help Center & Support',
    contactUs: 'Contact Us',
    contactUsText: 'Need assistance with your data pipeline or analytics dashboard? Our team is here to help. Please reach out to us at support@insightx.io and we will respond within 24 hours.',
    faq: 'FAQ',
    faq1q: 'How long does data processing take?',
    faq1a: 'Depending on the size of your CSV, it may take anywhere from a few seconds to several minutes.',
    faq2q: 'Can I upload multiple datasets?',
    faq2a: 'Yes, you can initiate a new analysis from the dashboard anytime.',

    // Terms
    termsTitle: 'Terms of Service',
    lastUpdatedTerms: 'Last Updated: April 2026',
    terms1Title: '1. Acceptance of Terms',
    terms1Text: 'By accessing and using InsightX, you agree to be bound by these Terms of Service. If you do not agree to these terms, please do not use our platform.',
    terms2Title: '2. Description of Service',
    terms2Text: 'InsightX provides AI-powered business analytics, forecasting, and data processing services. We reserve the right to modify or discontinue the service at any time.',
    terms3Title: '3. User Data',
    terms3Text: 'You retain all rights to the data you upload. InsightX only processes your data to provide analytics and insights directly to you, and does not share your raw data with third parties.',

    // Privacy
    privacyTitle: 'Privacy Policy',
    lastUpdatedPrivacy: 'Last Updated: April 2026',
    privacy1Title: '1. Information We Collect',
    privacy1Text: 'We collect information you provide directly to us, such as when you create an account, update your profile, or upload datasets for analysis.',
    privacy2Title: '2. How We Use Information',
    privacy2Text: 'We use the information we collect to provide, maintain, and improve our services, to process transactions, and to send you related information including confirmations and technical notices.',
    privacy3Title: '3. Data Security',
    privacy3Text: 'We take reasonable measures to help protect information about you from loss, theft, misuse, unauthorized access, disclosure, alteration, and destruction.',
  },
  ar: {
    language: 'اللغة',
    toggleTheme: 'تغيير المظهر',
    login: 'تسجيل الدخول',
    signup: 'إنشاء حساب',
    startFree: 'ابدأ التحليل مجانًا',
    viewDashboard: 'لوحة التحكم',
    tagline: 'اكتشف قوة',
    tagline2: 'تحليلات الأعمال بالذكاء الاصطناعي',
    description: 'حوّل بيانات مبيعاتك إلى رؤى قابلة للتنفيذ على الفور. قم برفع ملف CSV الخاص بك، ودع محرك الذكاء الاصطناعي لدينا يحلل الاتجاهات، واحصل على توقعات دقيقة لتنمية عملك.',
    noCard: 'لا يتطلب بطاقة ائتمان',
    freeTrial: 'تجربة مجانية لمدة 14 يومًا',
    featureStart: 'سهولة البدء',
    featureStartDesc: 'قم برفع ملف CSV الخاص بك وسيقوم محركنا بتعيين هيكل بياناتك تلقائيًا.',
    featureAnalytics: 'تحليلات عميقة',
    featureAnalyticsDesc: 'احصل على لوحات تحكم شاملة تعرض مؤشرات الأداء الرئيسية والاتجاهات.',
    featureForecasting: 'توقعات ذكية',
    featureForecastingDesc: 'توقع المبيعات واحتياجات المخزون المستقبلية باستخدام نماذج تعلم الآلة.',
    featureSegmentation: 'رؤى العملاء',
    featureSegmentationDesc: 'قم بتصنيف عملائك تلقائيًا بناءً على سلوك الشراء.',
    support: 'الدعم',
    terms: 'الشروط',
    privacy: 'الخصوصية',
    footer: '© 2026 إنسايت إكس. جميع الحقوق محفوظة.',

    // Login
    signInTitle: 'تسجيل الدخول إلى إنسايت إكس',
    signInDesc: 'وصول آمن إلى لوحة التحكم الخاصة بك',
    emailAddress: 'البريد الإلكتروني',
    password: 'كلمة المرور',
    forgotPassword: 'هل نسيت كلمة المرور؟',
    logInBtn: 'تسجيل الدخول',
    loggingInBtn: 'جاري تسجيل الدخول...',
    noAccount: "ليس لديك حساب؟",

    // Signup
    createAccountTitle: 'أنشئ حساب إنسايت إكس',
    createAccountDesc: 'انضم إلى آلاف الشركات التي تستخدم إنسايت إكس لتحليل البيانات.',
    fullName: 'الاسم الكامل / الشركة',
    workEmail: 'البريد الإلكتروني للعمل',
    confirmPassword: 'تأكيد كلمة المرور',
    signUpBtn: 'إنشاء حساب',
    signingUpBtn: 'جاري إنشاء الحساب...',
    haveAccount: 'لديك حساب بالفعل؟',
    helpCenter: 'مركز المساعدة',

    // Support
    helpCenterTitle: 'مركز المساعدة والدعم',
    contactUs: 'اتصل بنا',
    contactUsText: 'هل تحتاج إلى مساعدة بشأن بياناتك أو لوحة التحليلات؟ فريقنا هنا للمساعدة. يرجى التواصل معنا على support@insightx.io وسنرد عليك خلال 24 ساعة.',
    faq: 'الأسئلة الشائعة',
    faq1q: 'كم يستغرق وقت معالجة البيانات؟',
    faq1a: 'حسب حجم ملف CSV الخاص بك، قد يستغرق الأمر من بضع ثوانٍ إلى عدة دقائق.',
    faq2q: 'هل يمكنني رفع مجموعات بيانات متعددة؟',
    faq2a: 'نعم، يمكنك بدء تحليل جديد من لوحة التحكم في أي وقت.',

    // Terms
    termsTitle: 'شروط الخدمة',
    lastUpdatedTerms: 'آخر تحديث: أبريل 2026',
    terms1Title: '1. قبول الشروط',
    terms1Text: 'بوصولك إلى إنسايت إكس واستخدامك له، فإنك توافق على الالتزام بشروط الخدمة هذه. إذا كنت لا توافق على هذه الشروط، يرجى عدم استخدام منصتنا.',
    terms2Title: '2. وصف الخدمة',
    terms2Text: 'يوفر إنسايت إكس تحليلات أعمال وتوقعات ومعالجة بيانات مدعومة بالذكاء الاصطناعي. نحتفظ بالحق في تعديل أو إيقاف الخدمة في أي وقت.',
    terms3Title: '3. بيانات المستخدم',
    terms3Text: 'أنت تحتفظ بجميع الحقوق في البيانات التي تقوم برفعها. يقوم إنسايت إكس فقط بمعالجة بياناتك لتوفير التحليلات والرؤى لك مباشرة، ولا نشارك بياناتك الخام مع أطراف ثالثة.',

    // Privacy
    privacyTitle: 'سياسة الخصوصية',
    lastUpdatedPrivacy: 'آخر تحديث: أبريل 2026',
    privacy1Title: '1. المعلومات التي نجمعها',
    privacy1Text: 'نجمع المعلومات التي تقدمها لنا مباشرة، مثل عند إنشاء حساب، أو تحديث ملفك الشخصي، أو رفع مجموعات بيانات للتحليل.',
    privacy2Title: '2. كيف نستخدم المعلومات',
    privacy2Text: 'نستخدم المعلومات التي نجمعها لتقديم خدماتنا والحفاظ عليها وتحسينها، ولمعالجة المعاملات، ولإرسال المعلومات المتعلقة إليك بما في ذلك التأكيدات والإشعارات الفنية.',
    privacy3Title: '3. أمان البيانات',
    privacy3Text: 'نتخذ تدابير معقولة للمساعدة في حماية المعلومات المتعلقة بك من الفقدان والسرقة وسوء الاستخدام والوصول غير المصرح به والكشف والتعديل والتدمير.',
  },
} as const;

export type TranslationKey = keyof typeof translations.en;

/** Translate a key to the given locale, falling back to English. */
export function t(key: TranslationKey, locale: Locale): string {
  return (translations[locale] as Record<string, string>)[key]
    ?? (translations.en as Record<string, string>)[key]
    ?? key;
}

export { translations };
