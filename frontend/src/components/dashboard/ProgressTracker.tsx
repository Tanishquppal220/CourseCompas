import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function ProgressTracker() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <Card className="bg-card text-card-foreground p-8 rounded-xl shadow-none">
        <CardHeader className="p-0 mb-4">
          <CardTitle className="text-lg font-medium font-sans">Current CGPA</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="text-4xl font-heading tracking-tight mb-2">8.75</div>
          <Badge variant="outline" className="text-muted-foreground">Term 4</Badge>
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
