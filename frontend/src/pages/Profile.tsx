import { useAuth } from "../lib/authContext";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";

export const Profile = () => {
  const { user, logout } = useAuth();

  if (!user) {
    return <div className="p-8">Please log in to view your profile.</div>;
  }

  return (
    <div className="flex flex-col gap-6 p-8 max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold">Your Academic Profile</h1>
      
      <Card>
        <CardHeader>
          <CardTitle>Profile Details</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div><strong className="font-medium text-muted-foreground">Registration Number:</strong> {user.registration_number}</div>
          <div><strong className="font-medium text-muted-foreground">Program:</strong> {user.program || "Not set"}</div>
          <div><strong className="font-medium text-muted-foreground">Current Term:</strong> {user.current_term || "Not set"}</div>
          <div><strong className="font-medium text-muted-foreground">CGPA:</strong> {user.cgpa || "Not set"}</div>
          <Button variant="outline" className="w-fit mt-4" onClick={logout}>Sign Out</Button>
        </CardContent>
      </Card>

      <Card className="opacity-50">
        <CardHeader>
          <CardTitle>Upload Transcript (Coming Soon)</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground mb-4">
            In future versions, you'll be able to upload your university transcript here to automatically import all your completed courses and grades.
          </p>
          <Button disabled>Upload File</Button>
        </CardContent>
      </Card>
    </div>
  );
};
