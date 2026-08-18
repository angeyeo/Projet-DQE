import React from 'react';
import { FileUp, Calculator, Lock, FileSpreadsheet, Check } from 'lucide-react';

export default function Stepper({ currentStep, setStep, completedSteps }) {
  const steps = [
    { id: 1, title: '1. Plans & Saisie', desc: 'Fichiers .PLN et paramètres', icon: FileUp },
    { id: 2, title: '2. Calculs Structurels', desc: 'Descente de charge & sections', icon: Calculator },
    { id: 3, title: '3. Validation & Verrouillage', desc: 'Validation ingénieur & cadenas', icon: Lock },
    { id: 4, title: '4. Devis DQE & IA', desc: 'DEK quantitatif & exports', icon: FileSpreadsheet },
  ];

  return (
    <div className="stepper-container">
      {steps.map((step) => {
        const Icon = step.icon;
        const isActive = currentStep === step.id;
        const isCompleted = completedSteps.includes(step.id);

        return (
          <div
            key={step.id}
            className={`step-card ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}
            onClick={() => setStep(step.id)}
          >
            <div className="step-number">
              {isCompleted ? <Check size={18} /> : <Icon size={18} />}
            </div>
            <div className="step-info">
              <h4>{step.title}</h4>
              <p>{step.desc}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
