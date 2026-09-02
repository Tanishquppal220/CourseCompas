import React from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ProgressTracker } from "@/components/dashboard/ProgressTracker";
import { BookOpen, GraduationCap, Clock, MessageSquare } from "lucide-react";

export function Landing() {
  return (
    <div className="min-h-screen bg-background text-foreground font-sans">
      {/* Top Nav */}
      <nav className="flex items-center justify-between p-6 max-w-7xl mx-auto">
        <div className="flex items-center gap-2">
          <GraduationCap className="h-6 w-6 text-primary" />
          <span className="text-xl font-heading font-medium tracking-tight">CourseCompass</span>
        </div>
        <div className="flex gap-4">
          <Button variant="ghost">Features</Button>
          <Button variant="ghost">About</Button>
          <Link to="/chat">
            <Button>Open App</Button>
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="py-24 px-6 text-center max-w-4xl mx-auto">
        <h1 className="text-5xl md:text-6xl font-heading mb-6 tracking-tight leading-tight">
          Your Intelligent <br className="hidden md:block"/> Academic Partner.
        </h1>
        <p className="text-xl text-muted-foreground mb-10 max-w-2xl mx-auto">
          Navigate your LPU B.Tech CSE degree with confidence. Track progress, prepare for exams, and make informed elective choices based on your unique goals.
        </p>
        <div className="flex justify-center gap-4">
          <Link to="/chat">
            <Button size="lg" className="h-12 px-8 text-base">Start Chatting <MessageSquare className="ml-2 h-4 w-4" /></Button>
          </Link>
          <Button size="lg" variant="outline" className="h-12 px-8 text-base">View Progress</Button>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-20 bg-muted/30">
        <div className="max-w-7xl mx-auto px-6">
          <h2 className="text-3xl font-heading mb-12 text-center">Everything you need to succeed</h2>
          
          <div className="grid md:grid-cols-3 gap-8 mb-16">
            <div className="bg-card p-8 rounded-xl border">
              <BookOpen className="h-10 w-10 text-primary mb-4" />
              <h3 className="text-xl font-heading mb-2">Course Content Q&A</h3>
              <p className="text-muted-foreground">Instantly query syllabus details, learning outcomes, and recommended textbooks for any term.</p>
            </div>
            <div className="bg-card p-8 rounded-xl border">
              <Clock className="h-10 w-10 text-primary mb-4" />
              <h3 className="text-xl font-heading mb-2">Exam Preparation</h3>
              <p className="text-muted-foreground">Know exactly what's covered before the mid-term using the Instruction Plan and CA weightages.</p>
            </div>
            <div className="bg-card p-8 rounded-xl border">
              <GraduationCap className="h-10 w-10 text-primary mb-4" />
              <h3 className="text-xl font-heading mb-2">Elective Advisory</h3>
              <p className="text-muted-foreground">Make smart choices for your Open Minors and departmental electives based on historical data.</p>
            </div>
          </div>

          {/* Progress Tracker Preview */}
          <div className="mt-24">
            <h2 className="text-3xl font-heading mb-8 text-center">Stay on top of your academics</h2>
            <ProgressTracker />
          </div>
        </div>
      </section>
      
      {/* Footer */}
      <footer className="border-t py-12 text-center text-muted-foreground">
        <p>© 2026 CourseCompass. LPU B.Tech CSE (Batch 2024).</p>
      </footer>
    </div>
  );
}
