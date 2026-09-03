import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/context/AuthContext";

export function ProgressTracker() {
  const { user } = useAuth();
  
  const cgpa = user?.current_cgpa?.toFixed(2) || "N/A";
  const term = user?.current_term ? `Term ${user.current_term}` : "N/A";

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <Card className="bg-card text-card-foreground p-8 rounded-xl shadow-none">
        <CardHeader className="p-0 mb-4">
          <CardTitle className="text-lg font-medium font-sans">Current CGPA</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="text-4xl font-heading tracking-tight mb-2">{cgpa}</div>
          <Badge variant="outline" className="text-muted-foreground">{term}</Badge>
        </CardContent>
      </Card>
      
      <Card className="bg-card text-card-foreground p-8 rounded-xl shadow-none">
        <CardHeader className="p-0 mb-4">
          <CardTitle className="text-lg font-medium font-sans">Credits Completed</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="text-4xl font-heading tracking-tight mb-2">92 / 160</div>
          <div className="text-sm text-muted-foreground">57.5% to graduation</div>
        </CardContent>
      </Card>
      
      <Card className="bg-card text-card-foreground p-8 rounded-xl shadow-none">
        <CardHeader className="p-0 mb-4">
          <CardTitle className="text-lg font-medium font-sans">Next Milestone</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="text-2xl font-heading tracking-tight mb-2">Electives Selection</div>
          <div className="text-sm text-muted-foreground">Opens in 2 weeks</div>
        </CardContent>
      </Card>
    </div>
  );
}
