import { useEffect, useRef, useState } from 'react'
import { BookOpen, FileCheck2, FlaskConical, LockKeyhole } from 'lucide-react'
import { researchApi } from './services/api'

export default function AuthScreen({ onAuthenticated, notice = '' }) {
  const [mode, setMode] = useState('signin')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [googleClientId, setGoogleClientId] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const googleButton = useRef(null)

  useEffect(() => {
    researchApi.getAuthConfig()
      .then((config) => setGoogleClientId(config.google_client_id || ''))
      .catch(() => setGoogleClientId(''))
  }, [])

  useEffect(() => {
    if (!googleClientId || !googleButton.current) return undefined

    const initializeGoogle = () => {
      if (!globalThis.google?.accounts?.id || !googleButton.current) return
      globalThis.google.accounts.id.initialize({
        client_id: googleClientId,
        callback: async ({ credential }) => {
          setError('')
          setIsSubmitting(true)
          try {
            onAuthenticated(await researchApi.signInWithGoogle(credential))
          } catch (requestError) {
            setError(requestError.message || 'Google sign-in failed. Please try again.')
          } finally {
            setIsSubmitting(false)
          }
        },
      })
      googleButton.current.replaceChildren()
      globalThis.google.accounts.id.renderButton(googleButton.current, {
        type: 'standard',
        theme: 'outline',
        size: 'large',
        shape: 'rectangular',
        text: mode === 'signup' ? 'signup_with' : 'signin_with',
        width: 360,
      })
    }

    const existingScript = globalThis.document.querySelector('script[data-google-identity]')
    if (globalThis.google?.accounts?.id) {
      initializeGoogle()
      return undefined
    }
    if (existingScript) {
      existingScript.addEventListener('load', initializeGoogle)
      return () => existingScript.removeEventListener('load', initializeGoogle)
    }
    const script = globalThis.document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    script.dataset.googleIdentity = 'true'
    script.onload = initializeGoogle
    globalThis.document.head.appendChild(script)
    return () => {
      script.onload = null
    }
  }, [googleClientId, mode, onAuthenticated])

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)
    try {
      const user = mode === 'signup'
        ? await researchApi.registerAccount({ name: name.trim(), email: email.trim(), password })
        : await researchApi.signIn({ email: email.trim(), password })
      onAuthenticated(user)
    } catch (requestError) {
      setError(requestError.message || 'Could not sign in. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const switchMode = (nextMode) => {
    setMode(nextMode)
    setError('')
  }

  return (
    <main className="auth-screen">
      <section className="auth-story">
        <div className="brand auth-brand">
          <div className="brand-mark">p</div>
          <div><strong>PaperPilot</strong><small>research readiness</small></div>
        </div>
        <div className="auth-story-copy">
          <p className="kicker">YOUR RESEARCH WORKSPACE</p>
          <h1>Bring every paper closer to publication<span className="period">.</span></h1>
          <p>Analyze manuscripts, check journal fit, and prepare submission-ready documents — all in one private workspace.</p>
          <div className="auth-benefits">
            <div><span><BookOpen size={17} /></span><div><strong>One home for your manuscripts</strong><small>Your library stays tied to your account.</small></div></div>
            <div><span><FlaskConical size={17} /></span><div><strong>Research-focused analysis</strong><small>Review structure, references, and journal fit.</small></div></div>
            <div><span><FileCheck2 size={17} /></span><div><strong>Ready when you are</strong><small>Generate a formatted submission package.</small></div></div>
          </div>
        </div>
        <span className="auth-story-foot">Your manuscripts are only visible in your account.</span>
      </section>

      <section className="auth-form-side">
        <div className="auth-card">
          <div className="auth-card-heading">
            <span className="auth-lock"><LockKeyhole size={18} /></span>
            <p className="kicker">PRIVATE WORKSPACE</p>
            <h2>{mode === 'signup' ? 'Create your account' : 'Welcome back'}</h2>
            <p>{mode === 'signup' ? 'Set up your account to start organizing your research.' : 'Sign in to pick up where your research left off.'}</p>
          </div>

          {notice && <div className="auth-notice" role="status">{notice}</div>}
          <div className="auth-tabs" role="tablist" aria-label="Account access">
            <button type="button" role="tab" aria-selected={mode === 'signin'} className={mode === 'signin' ? 'selected' : ''} onClick={() => switchMode('signin')}>Sign in</button>
            <button type="button" role="tab" aria-selected={mode === 'signup'} className={mode === 'signup' ? 'selected' : ''} onClick={() => switchMode('signup')}>Create account</button>
          </div>

          <form className="auth-form" onSubmit={submit}>
            {mode === 'signup' && (
              <label>
                Full name
                <input autoComplete="name" required maxLength={80} value={name} onChange={(event) => setName(event.target.value)} placeholder="Your name" />
              </label>
            )}
            <label>
              Email address
              <input type="email" autoComplete="email" required maxLength={254} value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" />
            </label>
            <label>
              Password
              <input type="password" autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} required minLength={10} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} placeholder={mode === 'signup' ? 'At least 10 characters' : 'Your password'} />
            </label>
            {mode === 'signup' && <small className="auth-hint">Use at least 10 characters.</small>}
            {error && <div className="auth-error" role="alert">{error}</div>}
            <button type="submit" className="primary-button auth-submit" disabled={isSubmitting}>
              {isSubmitting ? 'Please wait…' : mode === 'signup' ? 'Create account' : 'Sign in'}
            </button>
          </form>

          <div className="auth-divider"><span>OR CONTINUE WITH</span></div>
          {googleClientId ? (
            <div className={isSubmitting ? 'google-button busy' : 'google-button'} ref={googleButton} />
          ) : (
            <button type="button" className="outline-button google-unavailable" disabled>Google sign-in · not configured</button>
          )}
          {!googleClientId && <p className="google-note">Google sign-in can be enabled by configuring a Web OAuth client ID.</p>}
        </div>
        <p className="auth-privacy-note">By continuing, your account is created for your personal research workspace.</p>
      </section>
    </main>
  )
}
