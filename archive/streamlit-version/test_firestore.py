#!/usr/bin/env python3
"""
Quick test script to verify Firestore connection and permissions.
Run this before starting the app to ensure everything is configured correctly.
"""

import os
import sys
from datetime import datetime

# Add app to path
sys.path.insert(0, os.path.dirname(__file__))

from google.cloud import firestore
from app.config import settings


def test_firestore_connection():
    """Test Firestore connection and basic operations"""

    print("=" * 60)
    print("Firestore Connection Test")
    print("=" * 60)
    print()

    # Step 1: Check configuration
    print("1. Checking configuration...")
    print(f"   Project ID: {settings.GCP_PROJECT_ID}")
    print(f"   Region: {settings.GCP_REGION}")
    print(f"   Credentials: {settings.GCP_CREDENTIALS_PATH}")
    print(f"   Environment: {settings.DEPLOYMENT_ENV}")
    print()

    # Step 2: Set credentials
    if not settings.IS_CLOUD and settings.GCP_CREDENTIALS_PATH:
        if not os.path.exists(settings.GCP_CREDENTIALS_PATH):
            print(f"✗ Credentials file not found: {settings.GCP_CREDENTIALS_PATH}")
            print("  Please update GCP_CREDENTIALS_PATH in .env")
            return False
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GCP_CREDENTIALS_PATH
        print(f"✓ Credentials file found")
        print()

    # Step 3: Connect to Firestore
    print("2. Connecting to Firestore...")
    try:
        db = firestore.Client(
            project=settings.GCP_PROJECT_ID,
            database=settings.FIRESTORE_DATABASE,
        )
        print("✓ Connection successful!")
        print()
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print()
        print("Troubleshooting:")
        print("1. Enable Firestore: https://console.cloud.google.com/firestore")
        print("2. Check service account permissions (needs 'Cloud Datastore User' role)")
        print("3. Verify credentials path in .env")
        return False

    # Step 4: Test write
    print("3. Testing write permissions...")
    try:
        test_ref = db.collection('_test').document('connection_test')
        test_ref.set({
            'timestamp': firestore.SERVER_TIMESTAMP,
            'test': True,
            'message': 'Connection test from test_firestore.py'
        })
        print("✓ Write successful!")
        print()
    except Exception as e:
        print(f"✗ Write failed: {e}")
        print()
        print("Troubleshooting:")
        print("1. Check service account has 'Cloud Datastore User' role")
        print("2. Verify Firestore security rules allow writes")
        return False

    # Step 5: Test read
    print("4. Testing read permissions...")
    try:
        doc = test_ref.get()
        if doc.exists:
            data = doc.to_dict()
            print("✓ Read successful!")
            print(f"   Data: {data}")
            print()
        else:
            print("✗ Document not found (unexpected)")
            return False
    except Exception as e:
        print(f"✗ Read failed: {e}")
        return False

    # Step 6: Cleanup
    print("5. Cleaning up test data...")
    try:
        test_ref.delete()
        print("✓ Cleanup successful!")
        print()
    except Exception as e:
        print(f"⚠ Cleanup failed (non-critical): {e}")
        print()

    # Step 7: Check collections
    print("6. Checking existing collections...")
    try:
        collections = list(db.collections())
        if collections:
            print(f"✓ Found {len(collections)} collection(s):")
            for collection in collections:
                if collection.id != '_test':  # Skip our test collection
                    count = len(list(collection.limit(5).stream()))
                    print(f"   - {collection.id} ({count}+ documents)")
            print()
        else:
            print("  No collections yet (will be created on first use)")
            print()
    except Exception as e:
        print(f"⚠ Could not list collections: {e}")
        print()

    # Success!
    print("=" * 60)
    print("✓ All tests passed! Firestore is ready to use.")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Deploy security rules: firebase deploy --only firestore:rules")
    print("   OR manually in console: https://console.cloud.google.com/firestore/rules")
    print("2. Start the app: ./start-dev.sh")
    print("3. Test in browser: http://localhost:8080")
    print()

    return True


if __name__ == "__main__":
    try:
        success = test_firestore_connection()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
