import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';

export const Onboarding = () => {
  const { updateProfile } = useAuth();
  const navigate = useNavigate();
  
  const [currentTerm, setCurrentTerm] = useState('1');
  const [currentCgpa, setCurrentCgpa] = useState('');
  const [programName, setProgramName] = useState('');
  const [admissionYear, setAdmissionYear] = useState(new Date().getFullYear().toString());
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await updateProfile({
        current_term: parseInt(currentTerm),
        current_cgpa: parseFloat(currentCgpa),
        program_name: programName,
        admission_year: parseInt(admissionYear),
      });
      navigate('/chat');
    } catch (err) {
      setError('Failed to save profile. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen items-center justify-center bg-gray-50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-2xl font-bold text-center">Complete Your Profile</CardTitle>
          <CardDescription className="text-center">
            Tell us a bit about your academic journey
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <div className="bg-red-50 text-red-500 p-3 rounded-md text-sm">
                {error}
              </div>
            )}
            
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="currentTerm">
                Current Term
              </label>
              <select
                id="currentTerm"
                value={currentTerm}
                onChange={(e) => setCurrentTerm(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                required
              >
                {[1, 2, 3, 4, 5, 6, 7, 8].map(term => (
                  <option key={term} value={term}>Term {term}</option>
                ))}
              </select>
            </div>
            
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="currentCgpa">
                Current CGPA
              </label>
              <Input
                id="currentCgpa"
                type="number"
                step="0.01"
                min="0"
                max="10"
                value={currentCgpa}
                onChange={(e) => setCurrentCgpa(e.target.value)}
                placeholder="e.g. 8.5"
                required
              />
            </div>
            
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="programName">
                Program Name
              </label>
              <Input
                id="programName"
                type="text"
                value={programName}
                onChange={(e) => setProgramName(e.target.value)}
                placeholder="e.g. B.Tech CSE"
                required
              />
            </div>
            
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="admissionYear">
                Admission Year
              </label>
              <Input
                id="admissionYear"
                type="number"
                min="2000"
                max="2100"
                value={admissionYear}
                onChange={(e) => setAdmissionYear(e.target.value)}
                placeholder="e.g. 2021"
                required
              />
            </div>
          </CardContent>
          <CardFooter>
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? 'Saving...' : 'Save and Continue'}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
};
