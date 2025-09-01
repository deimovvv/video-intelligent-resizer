'use client';

import { useEffect, useState } from 'react';

export default function InitialLoader() {
  const [isVisible, setIsVisible] = useState(true);
  const [progress, setProgress] = useState(0);
  const [particles, setParticles] = useState<Array<{
    left: number;
    top: number;
    delay: number;
    duration: number;
  }>>([]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(false);
    }, 2800);

    const progressInterval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) return 100;
        return prev + Math.random() * 15 + 5;
      });
    }, 120);

    setParticles(
      Array.from({ length: 50 }, () => ({
        left: Math.random() * 100,
        top: Math.random() * 100,
        delay: Math.random() * 3,
        duration: 2 + Math.random() * 2
      }))
    );

    return () => {
      clearTimeout(timer);
      clearInterval(progressInterval);
    };
  }, []);

  if (!isVisible) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black flex items-center justify-center">
      <div className="absolute inset-0 bg-gradient-to-br from-neutral-950 via-black to-neutral-900"></div>
      
      <div className="absolute inset-0">
        {particles.map((particle, i) => (
          <div
            key={i}
            className="absolute w-px h-px bg-neutral-400/15 animate-pulse"
            style={{
              left: `${particle.left}%`,
              top: `${particle.top}%`,
              animationDelay: `${particle.delay}s`,
              animationDuration: `${particle.duration}s`
            }}
          />
        ))}
      </div>

      <div className="relative z-10 text-center">
        <div className="mb-8">
          <div className="relative">
            <div className="w-20 h-20 mx-auto mb-6 rounded-full border-2 border-neutral-600/40 flex items-center justify-center">
              <div className="w-16 h-16 rounded-full border-2 border-transparent border-t-neutral-400 border-r-neutral-500 animate-spin"></div>
              <div className="absolute w-12 h-12 rounded-full border border-transparent border-t-neutral-300 animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }}></div>
            </div>
            
            <div className="absolute -top-2 -left-2 w-24 h-24 rounded-full bg-neutral-500/3 animate-pulse"></div>
            <div className="absolute -top-4 -left-4 w-28 h-28 rounded-full border border-neutral-500/8 animate-ping"></div>
          </div>
        </div>

        <div className="space-y-4">
          <h1 className="text-2xl font-light text-white tracking-wide">
            <span className="bg-gradient-to-r from-neutral-300 via-white to-neutral-400 bg-clip-text text-transparent">
              MediaMonks
            </span>
          </h1>
          
          <p className="text-neutral-400 text-sm font-mono">
            Inicializando sistema...
          </p>

          <div className="w-64 mx-auto mt-6">
            <div className="flex justify-between text-xs text-neutral-500 mb-2">
              <span>Cargando</span>
              <span>{Math.min(100, Math.round(progress))}%</span>
            </div>
            <div className="w-full bg-neutral-800 rounded-full h-1 overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-neutral-400 to-neutral-300 transition-all duration-300 ease-out relative"
                style={{ width: `${Math.min(100, progress)}%` }}
              >
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/15 to-transparent animate-pulse"></div>
              </div>
            </div>
          </div>

          <div className="mt-8 space-y-2">
            {[
              { text: "Conectando con API...", delay: 0 },
              { text: "Verificando componentes...", delay: 800 },
              { text: "Listo para procesar videos", delay: 1600 }
            ].map((item, i) => (
              <div
                key={i}
                className="text-xs text-neutral-500 font-mono opacity-0 animate-fade-in"
                style={{ animationDelay: `${item.delay}ms`, animationFillMode: 'forwards' }}
              >
                {item.text}
              </div>
            ))}
          </div>
        </div>
      </div>

      <style jsx>{`
        @keyframes fade-in {
          to {
            opacity: 1;
          }
        }
        .animate-fade-in {
          animation: fade-in 0.5s ease-out;
        }
      `}</style>
    </div>
  );
}