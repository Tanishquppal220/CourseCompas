import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { FieldGroup, Field, FieldLabel } from "../components/ui/field";

export const Register = () => {
  const [formData, setFormData] = useState({
    registration_number: "",
    password: "",
    cgpa: "",
    current_term: "",
    program: "",
  });
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const response = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...formData,
          cgpa: formData.cgpa ? parseFloat(formData.cgpa) : undefined,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Registration failed");
      }
      
      navigate("/login");
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="flex h-[80vh] items-center justify-center">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-2xl">Create Profile</CardTitle>
        </CardHeader>
        <form onSubmit={handleRegister}>
          <CardContent className="flex flex-col gap-4">
            {error && <div className="text-red-500 text-sm">{error}</div>}
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="reg-num">Registration Number</FieldLabel>
                <Input
                  id="reg-num"
                  value={formData.registration_number}
                  onChange={(e) => setFormData({...formData, registration_number: e.target.value})}
                  required
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="password">Password</FieldLabel>
                <Input
                  id="password"
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({...formData, password: e.target.value})}
                  required
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="program">Program</FieldLabel>
                <Input
                  id="program"
                  placeholder="e.g. B.Tech CSE"
                  value={formData.program}
                  onChange={(e) => setFormData({...formData, program: e.target.value})}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="term">Current Term</FieldLabel>
                <Input
                  id="term"
                  placeholder="e.g. Semester 5"
                  value={formData.current_term}
                  onChange={(e) => setFormData({...formData, current_term: e.target.value})}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="cgpa">CGPA</FieldLabel>
                <Input
                  id="cgpa"
                  type="number"
                  step="0.01"
                  placeholder="e.g. 8.5"
                  value={formData.cgpa}
                  onChange={(e) => setFormData({...formData, cgpa: e.target.value})}
                />
              </Field>
            </FieldGroup>
          </CardContent>
          <CardFooter>
            <Button type="submit" className="w-full">Register</Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
};
