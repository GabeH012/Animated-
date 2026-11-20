# sfx.py - slice the Higgsfield boom and synthesize the other effects; writes 48 kHz mono wavs to public/hurricane/sfx
import os, subprocess, numpy as np, wave

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, '..', '..', 'public', 'hurricane', 'sfx'))
os.makedirs(OUT, exist_ok=True)
SR = 48000
rng = np.random.default_rng(7)


def save(name, x, peak_db=-1.0):
    x = x / (np.abs(x).max() + 1e-9) * 10 ** (peak_db / 20)
    with wave.open(os.path.join(OUT, name + '.wav'), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    print(name, f'{len(x) / SR:.2f}s')


def lowpass(x, fc):
    # one-pole low-pass; fc may be an array (time-varying)
    fc = np.broadcast_to(np.asarray(fc, dtype=float), x.shape)
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.empty_like(x); s = 0.0
    for i in range(len(x)):
        s = (1 - a[i]) * x[i] + a[i] * s
        y[i] = s
    return y


def bandnoise(n, lo, hi):
    return lowpass(rng.standard_normal(n), hi) - lowpass(rng.standard_normal(n) * 0 + lowpass(rng.standard_normal(n), hi), lo)


def env_ad(n, attack, decay_pow=1.0):
    t = np.linspace(0, 1, n)
    a = np.clip(t / attack, 0, 1)
    d = np.clip((1 - t) / (1 - attack), 0, 1) ** decay_pow
    return a * d


# boom: slice Higgsfield file from its onset (0.70 s), fade the tail
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', os.path.join(HERE, 'sfx_raw', 'boom.mp3'), '-ac', '1', '-ar',
                      str(SR), '-f', 'f32le', '-'], capture_output=True, check=True).stdout
b = np.frombuffer(raw, dtype=np.float32)[int(0.69 * SR):].copy()
fade = np.ones_like(b); fl = int(1.2 * SR); fade[-fl:] = np.linspace(1, 0, fl) ** 2
save('boom', b * fade)
# small distant booms for the "every twenty minutes" counter: low-passed, shorter boom
sm = lowpass(b[:int(1.1 * SR)].astype(float), 500.0)
sm *= np.linspace(1, 0, len(sm)) ** 1.5
save('boom_small', sm)

# whoosh: noise through a sweeping low-pass, swelling then fading (peak at 45 %)
n = int(0.55 * SR)
t = np.linspace(0, 1, n)
sweep = 300 + 3200 * np.sin(np.pi * t) ** 2
x = lowpass(rng.standard_normal(n), sweep) * np.exp(-((t - 0.45) / 0.22) ** 2)
save('whoosh', x)

# storm wind bed: two layers of slowly modulated filtered noise (howl + rush), 16 s
n = int(16 * SR)
t = np.arange(n) / SR
mod = 0.6 + 0.25 * np.sin(2 * np.pi * 0.23 * t) + 0.15 * np.sin(2 * np.pi * 0.61 * t + 1)
howl = lowpass(rng.standard_normal(n), 380 + 260 * mod) - lowpass(rng.standard_normal(n), 120.0)
rush = lowpass(rng.standard_normal(n), 2200.0) * 0.25
x = (howl + rush) * mod
x[:SR // 2] *= np.linspace(0, 1, SR // 2)
save('wind', x)

# gust: a big swelling wind push for the fallout drift (2.4 s)
n = int(2.4 * SR)
t = np.linspace(0, 1, n)
x = lowpass(rng.standard_normal(n), 250 + 1500 * np.sin(np.pi * t) ** 1.5) * np.sin(np.pi * t) ** 1.2
save('gust', x)

# pop: eyes opening (short pitch-up blip)
n = int(0.12 * SR)
t = np.arange(n) / SR
f = 380 + 900 * t / t[-1]
x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 35)
save('pop', x)

# tick: clock ticks (short clicks)
n = int(0.04 * SR)
t = np.arange(n) / SR
x = (np.sin(2 * np.pi * 2400 * t) + 0.5 * np.sin(2 * np.pi * 3900 * t)) * np.exp(-t * 260)
save('tick', x)

# shimmer: rising ring for the shock wave passing (1.0 s filtered noise, high band)
n = int(1.0 * SR)
t = np.linspace(0, 1, n)
x = (rng.standard_normal(n) - lowpass(rng.standard_normal(n), 2500.0)) * np.exp(-((t - 0.25) / 0.2) ** 2)
x = lowpass(x, 6000.0)
save('shock', x)

# boing: scared reaction (falling-pitch wobble)
n = int(0.45 * SR)
t = np.arange(n) / SR
f = 520 * np.exp(-t * 2.2) * (1 + 0.08 * np.sin(2 * np.pi * 18 * t))
x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6)
save('boing', x)
